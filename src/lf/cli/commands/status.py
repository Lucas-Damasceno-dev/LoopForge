import click
from rich.console import Console
from rich.table import Table
from lf.config.loader import load_config
from lf.telemetry.store import TelemetryStore

console = Console()


@click.command(name="status")
def status_cmd():
    """Display project status and task telemetry breakdown."""
    config_path = Path(".loopforge.json")
    if not config_path.exists() and not config_path.with_suffix(".yaml").exists():
        console.print("[red]Error: Not a LoopForge project. Run 'loopforge init' first.[/red]")
        raise SystemExit(1)
    cfg = load_config()
    console.print(f"[bold blue]Project:[/bold blue] {cfg.project_name} ({cfg.project_id})")
    console.print(f"[bold blue]Stack:[/bold blue] {cfg.stack.language} ({cfg.stack.framework})")

    table = Table(title="Task Backlog Status")
    table.add_column("Task ID", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Attempts", justify="right")

    for task in cfg.plan.tasks:
        table.add_row(task.id, task.title, task.status, str(task.attempts))

    console.print(table)
