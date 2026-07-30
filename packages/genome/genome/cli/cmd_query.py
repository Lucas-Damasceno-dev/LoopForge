"""Subcomando genome query."""

import click
from rich.console import Console
from genome.core.scanner import GenomeScanner
from genome.store.sqlite import GenomeStore

console = Console()


@click.command(name="query")
@click.option("--where", help="Filtro determinístico (ex: 'dependents > 5').")
@click.option("--repo", default=".", help="Caminho do repositório.")
def query_cmd(where: str, repo: str):
    """Consulta módulos do genoma via filtros determinísticos."""
    store = GenomeStore(repo)
    genome = store.load_genome()
    if not genome:
        scanner = GenomeScanner(repo)
        genome = scanner.scan()

    console.print(f"[bold blue]🔎 Consulta de Genoma:[/bold blue] where='{where}'")
    results = []

    for mod in genome.modules:
        if where and "dependents >" in where:
            try:
                threshold = int(where.split(">")[1].strip())
                if len(mod.dependents) > threshold:
                    results.append(mod)
            except Exception:
                results.append(mod)
        else:
            results.append(mod)

    for mod in results[:10]:
        console.print(f"  - [cyan]{mod.path}[/cyan]: {len(mod.dependents)} dependentes, {len(mod.exports)} exports")
