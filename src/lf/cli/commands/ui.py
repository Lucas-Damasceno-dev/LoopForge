import click
import uvicorn
from rich.console import Console

console = Console()


@click.command(name="ui")
@click.option("--port", default=8000, help="Port to run the Web Dashboard server")
@click.option("--host", default="127.0.0.1", help="Host address for the Web Dashboard server")
def ui_cmd(port: int, host: str):
    """Launch the LoopForge v6 Web Dashboard UI server."""
    console.print(f"[bold green]🚀 Starting LoopForge Web Dashboard...[/bold green]")
    console.print(f"  [cyan]URL:[/cyan] [bold underline]http://{host}:{port}[/bold underline]")
    console.print(f"  [cyan]Dashboard:[/cyan] [bold underline]http://{host}:{port}/dashboard[/bold underline]\n")
    uvicorn.run("lf.api.app:create_app", host=host, port=port, factory=True, log_level="info")
