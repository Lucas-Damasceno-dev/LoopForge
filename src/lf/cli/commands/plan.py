import click
from rich.console import Console
from lf.config.loader import load_config, save_config
from lf.orchestrator.plan_creator import create_plan_from_vision

console = Console()


@click.command(name="plan")
@click.option("--vision", prompt="Project vision", help="High level project vision")
def plan_cmd(vision: str):
    """Generate a task execution plan from project vision."""
    try:
        cfg = load_config()
    except FileNotFoundError:
        console.print("[red]No .loopforge.json found. Run 'loopforge init' first.[/red]")
        raise SystemExit(1)
    plan = create_plan_from_vision(vision)
    cfg.plan = plan
    save_config(cfg)
    console.print(f"[bold green]Generated plan with {len(plan.tasks)} tasks.[/bold green]")
    for t in plan.tasks:
        console.print(f"  • [cyan]{t.id}[/cyan]: {t.title}")
