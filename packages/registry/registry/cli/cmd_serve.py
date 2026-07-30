"""Subcomando registry serve."""

import click
import uvicorn
from registry.server.app import create_registry_app


@click.command(name="serve")
@click.option("--port", default=8081, help="Porta do servidor HTTP.")
@click.option("--host", default="0.0.0.0", help="Host do servidor HTTP.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def serve_cmd(port: int, host: str, repo: str):
    """Inicia o servidor HTTP REST do Agentic Interface Registry."""
    app = create_registry_app(repo_root=repo)
    uvicorn.run(app, host=host, port=port)
