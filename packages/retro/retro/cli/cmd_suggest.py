"""Subcomando retro suggest."""

import click
from rich.console import Console
from retro.store.sqlite import RetroStore

console = Console()


@click.command(name="suggest")
@click.option("--next-task", required=True, help="Descrição da próxima tarefa.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def suggest_cmd(next_task: str, repo: str):
    """Sugere melhorias e overrides de prompt para a próxima tarefa com base no histórico."""
    store = RetroStore(repo)
    learnings = store.list_learnings()

    console.print(f"[bold blue]💡 Sugestões do Retro para a Tarefa:[/bold blue] [cyan]{next_task}[/cyan]")
    if not learnings:
        console.print("  - Nenhuma sugestão histórica acumulada. Use as configurações recomendadas da stack.")
        return

    for l in learnings:
        console.print(f"  - [[yellow]{l.category.upper()}[/yellow]] {l.recommendation}")
        if l.prompt_override:
            console.print(f"    • Prompt Override: [green]'{l.prompt_override}'[/green]")
