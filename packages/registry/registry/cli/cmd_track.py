"""Subcomando registry track."""

import click
from rich.console import Console
from registry.core.scanner import InterfaceScanner
from registry.store.sqlite import RegistryStore

console = Console()


@click.command(name="track")
@click.argument("path", default=".")
@click.option("--agent", default="developer", help="Nome do agente responsável pelas edições.")
def track_cmd(path: str, agent: str):
    """Mapeia e registra todas as interfaces públicas do codebase."""
    console.print(f"[bold blue]🔗 Mapeando interfaces em:[/bold blue] [cyan]{path}[/cyan] (Agente: [yellow]{agent}[/yellow])...")
    scanner = InterfaceScanner(path)
    schema = scanner.scan(current_agent=agent)
    store = RegistryStore(path)
    store.save(schema)
    console.print(f"[bold green]✓ Mapeamento concluído![/bold green] Total: [yellow]{len(schema.interfaces)}[/yellow] interfaces registradas.")
