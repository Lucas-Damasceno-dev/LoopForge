"""Subcomando retro list."""

import click
from rich.console import Console
from retro.store.sqlite import RetroStore

console = Console()


@click.command(name="list")
@click.option("--repo", default=".", help="Caminho do repositório.")
def list_cmd(repo: str):
    """Lista o histórico de sessões analisadas pelo Retro."""
    store = RetroStore(repo)
    sessions = store.list_sessions()

    if not sessions:
        console.print("[yellow]Nenhuma sessão registrada no histórico do Retro.[/yellow]")
        return

    console.print(f"[bold blue]🧠 Histórico de Sessões ({len(sessions)}):[/bold blue]")
    for s in sessions[:15]:
        status_color = "green" if s.status == "PASS" else "red"
        dur_fmt = f"{s.duration_ms / 1000.0:.1f}s"
        console.print(
            f"  - [{status_color}]{s.session_id}[/{status_color}] | Goal: [cyan]{s.goal[:40]}[/cyan] | Status: {s.status} | Duração: {dur_fmt} | Custo: ${s.cost:.2f}"
        )
