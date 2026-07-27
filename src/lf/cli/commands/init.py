import click
from rich.console import Console
from lf.config.loader import save_config
from lf.config.schema import LoopForgeConfig, TechStack

console = Console()


@click.command(name="init")
@click.option("--name", default="LoopForge Project", help="Project name")
@click.option("--stack", default="python", help="Primary tech stack language")
def init_cmd(name: str, stack: str):
    """Initialize a new LoopForge v6 project configuration."""
    cfg = LoopForgeConfig(
        project_id=name.lower().replace(" ", "_"),
        project_name=name,
        stack=TechStack(language=stack),
    )
    p = save_config(cfg)
    console.print(f"[bold green]Initialized LoopForge project config at {p}[/bold green]")
