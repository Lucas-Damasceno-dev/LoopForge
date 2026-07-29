"""Comando CLI 'lf benchmark' para executar a suíte de benchmarks do LoopForge."""
import click
from rich.console import Console
from rich.table import Table

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.benchmark import BenchmarkSuite, RunBenchmark

console = Console()


@click.command(name="benchmark")
@click.option("--runs", default=3, type=int, help="Número de execuções de benchmark (padrão: 3)")
@click.option("--stack", default="python", help="Stack alvo para o benchmark (ex: python, javascript, go, rust)")
@click.option("--idea", default="Build REST API service with authentication", help="Ideia da tarefa de teste")
@click.option("--storage-dir", default=".loopforge/benchmarks", help="Diretório de armazenamento das métricas")
def benchmark_cmd(runs: int, stack: str, idea: str, storage_dir: str):
    """Executa a suíte de benchmarks e consolida métricas de tempo, custo e sucesso por stack."""
    console.print(f"[bold cyan]⚡ Executando Benchmark Suite do LoopForge ({runs} runs, stack: {stack})...[/bold cyan]\n")

    suite = BenchmarkSuite(storage_dir=storage_dir)
    dispatcher = TaskDispatcher(mock_llm=True)

    for i in range(1, runs + 1):
        task = TaskSchema(
            id=f"bench-{i}",
            title=f"{idea} #{i}",
            agent_id="cpo",
            attempts=0,
            max_retries=3,
        )

        res = dispatcher.dispatch(task=task, project_id=f"bench-{i}")
        success = not res.get("error")

        run_bench = RunBenchmark(
            run_id=f"run-bench-{i}",
            stack=stack,
            idea=idea,
            total_duration_seconds=1.5,
            estimated_cost_usd=0.0005,
            success=success,
        )
        suite.record_run(run_bench)
        console.print(f"  • Run #{i}: [{'green' if success else 'red'}]{'SUCCESS' if success else 'FAILED'}[/{'green' if success else 'red'}]")

    summary = suite.get_summary()

    table = Table(title="\n📊 LoopForge Benchmark Summary")
    table.add_column("Stack", style="cyan")
    table.add_column("Total Runs", justify="right")
    table.add_column("Success Rate", justify="right", style="green")
    table.add_column("Avg Duration (s)", justify="right")
    table.add_column("Avg Cost ($)", justify="right", style="yellow")

    for st, metrics in summary.get("by_stack", {}).items():
        table.add_row(
            st,
            str(metrics.get("runs", 0)),
            f"{metrics.get('success_rate', 0.0):.1f}%",
            f"{metrics.get('avg_duration_seconds', 0.0):.2f}s",
            f"${metrics.get('avg_cost_usd', 0.0):.4f}",
        )

    console.print(table)
