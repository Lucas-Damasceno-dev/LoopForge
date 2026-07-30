"""Subcomando genome diff."""

import click
from rich.console import Console
from genome.core.diff import diff_genomes
from genome.core.scanner import GenomeScanner
from genome.store.sqlite import GenomeStore

console = Console()


@click.command(name="diff")
@click.option("--since", default="HEAD", help="Ref do Git para comparação.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def diff_cmd(since: str, repo: str):
    """Compara o genoma atual com uma versão anterior."""
    scanner = GenomeScanner(repo)
    new_genome = scanner.scan()
    store = GenomeStore(repo)
    old_genome = store.load_genome()

    if not old_genome:
        console.print("[yellow]Sem genoma anterior em cache para comparar.[/yellow]")
        return

    diff = diff_genomes(old_genome, new_genome)
    console.print(f"[bold blue]🧬 Diff de Genoma (since {since}):[/bold blue]")
    console.print(f"  • Arquivos Adicionados: {len(diff['added_files'])}")
    console.print(f"  • Arquivos Removidos: {len(diff['removed_files'])}")
    console.print(f"  • Novos Exports: {len(diff['new_exports'])}")
    console.print(f"  • Exports Removidos: {len(diff['removed_exports'])}")
    console.print(f"  • Delta Bus Factor Score: {diff['bus_score_delta']}")
    console.print(f"  • Novas Violações de Camada: {diff['new_layer_violations']}")
