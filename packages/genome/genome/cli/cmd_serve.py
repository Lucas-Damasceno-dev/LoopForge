"""Subcomando genome serve."""

import click
import uvicorn
from genome.server.app import create_genome_app


@click.command(name="serve")
@click.option("--port", default=8080, help="Porta do servidor HTTP.")
@click.option("--host", default="0.0.0.0", help="Host do servidor HTTP.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def serve_cmd(port: int, host: str, repo: str):
    """Inicia o servidor HTTP REST para servir o genoma a agentes e IDEs."""
    app = create_genome_app(repo_root=repo)
    uvicorn.run(app, host=host, port=port)
