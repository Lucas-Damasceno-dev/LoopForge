"""Comando CLI 'lf benchmark' para executar a suíte de benchmarks ELO do LoopForge."""

import json
import os
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from lf.config.loader import load_config
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.benchmark import BenchmarkSuite, RunBenchmark
from lf.telemetry.benchmark_dataset import CURATED_BENCHMARK_PROBLEMS
from lf.telemetry.costs import query_llm_costs_since, snapshot_llm_cost_watermark

console = Console()

RESULT_SCHEMA_VERSION = "1.0"


def _resolve_model(mock: bool) -> str:
    """Resolve o nome do modelo em uso (env > config > default)."""
    if mock:
        return "mock"
    env_model = os.environ.get("OPENROUTER_MODEL") or os.environ.get("OPENCODE_MODEL")
    if env_model:
        return env_model
    try:
        cfg_model = getattr(load_config(), "llm_model", None)
    except Exception:
        cfg_model = None
    return cfg_model or "oc/deepseek-v4-flash-free"


def _cost_stats(values: list) -> dict:
    """Agrega custos por run: média/desvio/total. 'n/a' quando nada foi medido."""
    available = [v for v in values if isinstance(v, (int, float))]
    if not available:
        return {"available": False, "mean": "n/a", "std": "n/a", "total": "n/a"}
    mean = sum(available) / len(available)
    std = statistics.stdev(available) if len(available) >= 2 else 0.0
    return {
        "available": True,
        "mean": round(mean, 6),
        "std": round(std, 6),
        "total": round(sum(available), 6),
    }


def _duration_stats(values: list[float]) -> dict:
    return {
        "mean": round(sum(values) / len(values), 2) if values else 0.0,
        "std": round(statistics.stdev(values), 2) if len(values) >= 2 else 0.0,
    }


def _build_results(
    model: str,
    mock: bool,
    runs: int,
    limit: int,
    storage_dir: str,
    elo: tuple[float, float, float],
    per_problem: dict,
    per_stack: dict,
    total_cost: float | str,
) -> dict:
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "model_version": "n/a",
        "mock": mock,
        "runs": runs,
        "limit": limit,
        "storage_dir": storage_dir,
        "elo": {"previous": elo[0], "new": elo[1], "delta": elo[2]},
        "total_cost_usd": total_cost,
        "per_problem": per_problem,
        "per_stack": per_stack,
    }


def _build_markdown_report(results: dict) -> str:
    """Gera relatório markdown legível: ELO × custo × stack × variância."""
    lines = [
        "# LoopForge Benchmark Report",
        "",
        f"- **Data:** {results['generated_at']}",
        f"- **Modelo:** {results['model']}",
        f"- **Model version:** {results.get('model_version', 'n/a')}",
        f"- **Runs por problema:** {results['runs']}",
        f"- **Modo mock:** {'sim' if results['mock'] else 'não'}",
        f"- **Custo total (USD):** {results['total_cost_usd']}",
        "",
        "## ELO Rating",
        "",
        f"- Anterior: {results['elo']['previous']:.1f}",
        f"- Novo: {results['elo']['new']:.1f}",
        f"- Delta: {results['elo']['delta']:+.1f}",
        "",
        "## Resumo por stack",
        "",
        "| Stack | Runs | Taxa de sucesso | Custo médio (USD) | Desvio custo | Tempo médio (s) | Desvio tempo |",
        "|---|---|---|---|---|---|---|",
    ]
    for st, m in sorted(results["per_stack"].items()):
        lines.append(
            f"| {st} | {m['runs']} | {m['success_rate']:.1f}% | "
            f"{m['cost_mean']} | {m['cost_std']} | {m['duration_mean']} | {m['duration_std']} |"
        )
    lines += [
        "",
        "## Detalhe por problema",
        "",
        "| Problema | Stack | Sucesso | Custo médio (USD) | Tempo médio (s) | Desvio (s) |",
        "|---|---|---|---|---|---|",
    ]
    for pid, p in sorted(results["per_problem"].items()):
        lines.append(
            f"| {pid} | {p['stack']} | {p['success_rate']:.0f}% ({p['successful']}/{p['runs']}) | "
            f"{p['cost_mean']} | {p['duration_mean']} | {p['duration_std']} |"
        )
    lines += [
        "",
        "## Detalhe por execução",
        "",
        "| Run | Problema | Stack | Sucesso | Custo (USD) | Duração (s) | Modelo |",
        "|---|---|---|---|---|---|---|",
    ]
    for pid, p in sorted(results["per_problem"].items()):
        for r in p["records"]:
            lines.append(
                f"| {r['run']} | {pid} | {p['stack']} | {'✅' if r['success'] else '❌'} | "
                f"{r['cost_usd']} | {r['duration_seconds']} | {r['model']} |"
            )
    return "\n".join(lines) + "\n"


@click.command(name="benchmark")
@click.option("--limit", default=10, type=int, help="Número de problemas curados a executar (padrão: 10)")
@click.option("--runs", default=1, type=int, help="Repetições por problema (padrão: 1) — mede média/desvio/variância")
@click.option(
    "--mock/--no-mock", default=False, help="Executar em modo LLM mock (smoke test rápido) — requer flag explícita"
)
@click.option(
    "--storage-dir", default=".loopforge/benchmarks", help="Diretório de armazenamento do histórico ELO e artefatos"
)
def benchmark_cmd(limit: int, runs: int, mock: bool, storage_dir: str):
    """Executa a suíte curada de benchmarks e mede a pontuação ELO do pipeline."""
    if runs < 1:
        raise click.BadParameter("--runs deve ser >= 1")

    problems = CURATED_BENCHMARK_PROBLEMS[:limit]
    model = _resolve_model(mock)
    console.print(
        f"[bold cyan]⚡ Executando LoopForge ELO Benchmark Suite "
        f"({len(problems)} problemas × {runs} run(s), modelo: {model})...[/bold cyan]\n"
    )
    if mock:
        console.print("[bold yellow]⚠ Modo MOCK (smoke test) — custos não são medidos.[/bold yellow]")

    suite = BenchmarkSuite(storage_dir=storage_dir)
    dispatcher = TaskDispatcher(mock_llm=mock)

    per_problem: dict[str, dict] = {}
    per_run_records: list[dict] = []
    costs: list = []
    passed_count = 0
    total_runs = 0

    for prob in problems:
        durations: list[float] = []
        prob_costs: list = []
        successes: list[bool] = []
        prob_models: set[str] = set()

        for i in range(runs):
            t0 = time.time()
            # project_id único por repetição: o AsyncSqliteSaver retoma o mesmo
            # thread_id em re-dispatch — sem id único, a 2ª repetição reexecutaria
            # o checkpoint da 1ª (cache de trajetória), invalidando a variância.
            watermark = snapshot_llm_cost_watermark()
            task = TaskSchema(
                id=prob.id,
                title=prob.title,
                agent_id="cpo",
                stack=prob.stack,
            )
            try:
                res = dispatcher.dispatch(task=task, project_id=f"bench-{prob.id}-{i + 1}")
            except Exception as e:
                res = {"error": str(e), "test_report": {}}
            dur = round(time.time() - t0, 2)
            durations.append(dur)

            test_report = res.get("test_report", {})
            failed_tests = test_report.get("summary", {}).get("tests_failed", 0) if isinstance(test_report, dict) else 0
            success = not res.get("error") and failed_tests == 0
            successes.append(success)
            total_runs += 1
            if success:
                passed_count += 1

            cost_info = query_llm_costs_since(watermark)
            cost = round(cost_info["total_cost_usd"], 6) if cost_info["available"] else "n/a"
            costs.append(cost)
            prob_costs.append(cost)
            prob_models.update(cost_info["models"] or [model])

            run_record = {
                "run": i + 1,
                "success": success,
                "duration_seconds": dur,
                "cost_usd": cost,
                "model": ", ".join(sorted(cost_info["models"])) if cost_info["models"] else model,
            }
            per_run_records.append({"problem_id": prob.id, **run_record})

            suite.record_run(
                RunBenchmark(
                    run_id=f"{prob.id}-{i + 1}",
                    stack=prob.stack,
                    idea=prob.idea,
                    total_duration_seconds=dur,
                    estimated_cost_usd=cost if isinstance(cost, float) else 0.0,
                    success=success,
                    model=str(run_record["model"]),
                )
            )

            status_str = "[bold green]PASS[/bold green]" if success else "[bold red]FAIL[/bold red]"
            console.print(f"  • [{prob.id}] run {i + 1}/{runs} → {status_str} ({dur}s)")

        cost_stats = _cost_stats(costs)
        dur_stats = _duration_stats(durations)
        prob_records = [r for r in per_run_records if r["problem_id"] == prob.id]
        per_problem[prob.id] = {
            "problem_id": prob.id,
            "title": prob.title,
            "stack": prob.stack,
            "runs": runs,
            "successful": sum(1 for s in successes if s),
            "success_rate": (sum(1 for s in successes if s) / runs) * 100 if runs else 0.0,
            "duration_mean": dur_stats["mean"],
            "duration_std": dur_stats["std"],
            "cost_mean": cost_stats["mean"],
            "cost_std": cost_stats["std"],
            "cost_total": cost_stats["total"],
            "models": sorted(prob_models),
            "records": prob_records,
        }

    elo_delta = suite.calculate_elo_delta(passed=passed_count, total=total_runs)
    prev_elo, new_elo = suite.update_elo_rating(elo_delta, model=model)

    # Agregação por stack a partir dos registros de execução (variância real)
    stacks: dict[str, dict] = {}
    for r in per_run_records:
        st = next(p["stack"] for p in per_problem.values() if p["problem_id"] == r["problem_id"])
        entry = stacks.setdefault(st, {"runs": 0, "successful": 0, "durations": [], "costs": []})
        entry["runs"] += 1
        if r["success"]:
            entry["successful"] += 1
        entry["durations"].append(r["duration_seconds"])
        if isinstance(r["cost_usd"], (int, float)):
            entry["costs"].append(r["cost_usd"])
    per_stack: dict[str, dict] = {}
    for st, metrics in stacks.items():
        cs = _cost_stats(metrics["costs"])
        ds = _duration_stats(metrics["durations"])
        per_stack[st] = {
            "runs": metrics["runs"],
            "success_rate": (metrics["successful"] / metrics["runs"]) * 100 if metrics["runs"] else 0.0,
            "cost_mean": cs["mean"],
            "cost_std": cs["std"],
            "duration_mean": ds["mean"],
            "duration_std": ds["std"],
        }

    total_cost: float | str = "n/a"
    measured = [c for c in costs if isinstance(c, (int, float))]
    if measured:
        total_cost = round(sum(measured), 6)

    results = _build_results(
        model=model,
        mock=mock,
        runs=runs,
        limit=limit,
        storage_dir=storage_dir,
        elo=(prev_elo, new_elo, elo_delta),
        per_problem=per_problem,
        per_stack=per_stack,
        total_cost=total_cost,
    )

    artifacts_dir = Path(storage_dir)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    results_path = artifacts_dir / "results.json"
    report_path = artifacts_dir / "benchmark_report.md"
    results_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    report_path.write_text(_build_markdown_report(results), encoding="utf-8")

    delta_color = "green" if elo_delta >= 0 else "red"
    sign = "+" if elo_delta >= 0 else ""

    table = Table(title="\n📊 LoopForge Benchmark & ELO Rating Summary")
    table.add_column("Stack", style="cyan")
    table.add_column("Runs", justify="right")
    table.add_column("Taxa de Sucesso", justify="right", style="green")
    table.add_column("Tempo Médio", justify="right")
    table.add_column("Desvio Tempo", justify="right")
    table.add_column("Custo Médio", justify="right", style="yellow")

    for st, metrics in per_stack.items():
        table.add_row(
            st,
            str(metrics.get("runs", 0)),
            f"{metrics.get('success_rate', 0.0):.1f}%",
            f"{metrics.get('duration_mean', 0.0):.2f}s",
            f"±{metrics.get('duration_std', 0.0):.2f}s",
            str(metrics.get("cost_mean", "n/a")),
        )

    console.print(table)
    console.print(
        f"\n🏆 [bold white]LoopForge Pipeline ELO Rating:[/bold white] "
        f"[bold gold1]{new_elo:.1f}[/bold gold1] "
        f"([{delta_color}]{sign}{elo_delta:.1f} ELO[/{delta_color}] de {prev_elo:.1f})\n"
    )
    console.print(f"📦 [bold green]Artefatos gerados:[/bold green] {results_path} e {report_path}\n")
