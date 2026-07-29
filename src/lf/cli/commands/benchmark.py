"""Comando CLI 'lf benchmark' para executar a suíte de benchmarks ELO do LoopForge."""
import time
import click
from rich.console import Console
from rich.table import Table

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.benchmark import BenchmarkSuite, RunBenchmark
from lf.telemetry.benchmark_dataset import CURATED_BENCHMARK_PROBLEMS

console = Console()


@click.command(name="benchmark")
@click.option("--limit", default=10, type=int, help="Número de problemas curados a executar (padrão: 10)")
@click.option("--mock", is_flag=True, default=True, help="Executar em modo LLM mock para testes ultrarrápidos")
@click.option("--storage-dir", default=".loopforge/benchmarks", help="Diretório de armazenamento do histórico ELO")
def benchmark_cmd(limit: int, mock: bool, storage_dir: str):
    """Executa a suíte curada de benchmarks e mede a pontuação ELO do pipeline."""
    problems = CURATED_BENCHMARK_PROBLEMS[:limit]
    console.print(f"[bold cyan]⚡ Executando LoopForge ELO Benchmark Suite ({len(problems)} problemas curados)...[/bold cyan]\n")

    suite = BenchmarkSuite(storage_dir=storage_dir)
    dispatcher = TaskDispatcher(mock_llm=mock)

    passed_count = 0
    total_duration = 0.0

    for prob in problems:
        t0 = time.time()
        task = TaskSchema(
            id=prob.id,
            title=prob.title,
            agent_id="cpo",
            stack=prob.stack,
            user_stories=prob.user_stories,
        )

        res = dispatcher.dispatch(task=task, project_id=f"bench-{prob.id}")
        dur = round(time.time() - t0, 2)
        total_duration += dur

        test_report = res.get("test_report", {})
        failed_tests = test_report.get("summary", {}).get("tests_failed", 0) if isinstance(test_report, dict) else 0
        success = not res.get("error") and failed_tests == 0

        if success:
            passed_count += 1

        run_bench = RunBenchmark(
            run_id=prob.id,
            stack=prob.stack,
            idea=prob.idea,
            total_duration_seconds=dur,
            estimated_cost_usd=0.001 if not mock else 0.0,
            success=success,
        )
        suite.record_run(run_bench)

        status_str = "[bold green]PASS[/bold green]" if success else "[bold red]FAIL[/bold red]"
        console.print(f"  • [{prob.id}] {prob.title} ({prob.stack.upper()}) → {status_str} ({dur}s)")

    # ELO Calculation
    elo_delta = suite.calculate_elo_delta(passed=passed_count, total=len(problems))
    prev_elo, new_elo = suite.update_elo_rating(elo_delta)

    delta_color = "green" if elo_delta >= 0 else "red"
    sign = "+" if elo_delta >= 0 else ""

    summary = suite.get_summary()

    table = Table(title="\n📊 LoopForge Benchmark & ELO Rating Summary")
    table.add_column("Stack", style="cyan")
    table.add_column("Problemas", justify="right")
    table.add_column("Taxa de Sucesso", justify="right", style="green")
    table.add_column("Tempo Médio", justify="right")
    table.add_column("Custo Estimado", justify="right", style="yellow")

    for st, metrics in summary.get("by_stack", {}).items():
        table.add_row(
            st,
            str(metrics.get("runs", 0)),
            f"{metrics.get('success_rate', 0.0):.1f}%",
            f"{metrics.get('avg_duration_seconds', 0.0):.2f}s",
            f"${metrics.get('avg_cost_usd', 0.0):.4f}",
        )

    console.print(table)
    console.print(
        f"\n🏆 [bold white]LoopForge Pipeline ELO Rating:[/bold white] "
        f"[bold gold1]{new_elo:.1f}[/bold gold1] "
        f"([{delta_color}]{sign}{elo_delta:.1f} ELO[/{delta_color}] de {prev_elo:.1f})\n"
    )
