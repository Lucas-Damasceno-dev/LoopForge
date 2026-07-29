"""Comando oficial CLI 'lf serve' para subir a API REST, WebSockets e Dashboard Web UI."""
import os
import secrets
import click
import uvicorn
from rich.console import Console

console = Console()


@click.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Endereço de host (padrão: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Porta HTTP (padrão: 8000)")
@click.option("--reload", is_flag=True, help="Ativa modo auto-reload para desenvolvimento")
def serve_cmd(host: str, port: int, reload: bool):
    """Inicia o servidor de API REST, WebSockets e Web Dashboard do LoopForge v6."""
    api_key = os.getenv("LF_API_API_KEY") or os.getenv("LF_API_KEY")
    if not api_key:
        api_key = secrets.token_hex(16)
        os.environ["LF_API_API_KEY"] = api_key

    console.print(f"[bold cyan]⚡ Iniciando LoopForge Server em http://{host}:{port}[/bold cyan]")
    console.print(f"[dim]   • Web Dashboard UI: http://{host}:{port}/dashboard[/dim]")
    console.print(f"[dim]   • API Documentation: http://{host}:{port}/docs[/dim]")
    console.print(f"[dim]   • WebSocket Streaming: ws://{host}:{port}/ws/streaming[/dim]")
    console.print(f"[bold green]🔐 Autenticação Ativada. X-API-Key:[/bold green] [bold white]{api_key}[/bold white]\n")

    uvicorn.run(
        "lf.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
