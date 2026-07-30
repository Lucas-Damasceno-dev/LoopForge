"""Subcomando retro feed."""

import click
from rich.console import Console
from retro.store.sqlite import RetroStore

console = Console()


@click.command(name="feed")
@click.option("--session-id", required=True, help="ID da sessão para alimentar os aprendizados.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def feed_cmd(session_id: str, repo: str):
    """Alimenta os aprendizados de uma sessão no banco persistente de lições."""
    store = RetroStore(repo)
    session = store.load_session(session_id)

    if not session:
        console.print(f"[bold red]Erro:[/bold red] Sessão '{session_id}' não encontrada.")
        return

    if not session.learnings:
        console.print("[yellow]Nenhum aprendizado registrado para esta sessão.[/yellow]")
        return

    store.add_learnings(session.learnings)
    console.print(
        f"[bold green]✓ {len(session.learnings)} aprendizado(s) registrado(s) com sucesso no cache do sistema![/bold green]"
    )
