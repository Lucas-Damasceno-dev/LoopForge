"""Subcomando genome check."""

import click
from rich.console import Console
from genome.core.scanner import GenomeScanner
from genome.store.sqlite import GenomeStore

console = Console()


@click.command(name="check")
@click.argument("file_path")
@click.option("--repo", default=".", help="Caminho do repositório.")
def check_cmd(file_path: str, repo: str):
    """Verifica se um arquivo viola regras semânticas/arquiteturais do repositório."""
    store = GenomeStore(repo)
    genome = store.load_genome()
    if not genome:
        scanner = GenomeScanner(repo)
        genome = scanner.scan()

    mod = next((m for m in genome.modules if m.path == file_path), None)
    if not mod:
        console.print(f"[bold red]Erro:[/bold red] Arquivo '{file_path}' não foi encontrado no genoma.")
        return

    console.print(f"[bold blue]🔍 Análise do Arquivo:[/bold blue] [cyan]{file_path}[/cyan]")
    console.print(f"  • Linhas: {mod.lines_count}")
    console.print(f"  • Exports: {len(mod.exports)}")
    console.print(f"  • Dependentes: {len(mod.dependents)}")
    console.print(f"  • Instabilidade: {mod.instability}")

    violations = [v for v in genome.architecture.layer_violations if v.from_path == file_path]
    if violations:
        console.print("[bold red]⚠️ Violações de Camada Arquitetural:[/bold red]")
        for v in violations:
            console.print(f"  - Importa `{v.to_path}` ({v.type})")
    else:
        console.print("[bold green]✓ Nenhuma violação de camada detectada.[/bold green]")

    is_bus_risk = any(hrf.path == file_path for hrf in genome.architecture.bus_factor.high_risk_files)
    if is_bus_risk:
        console.print("[bold yellow]⚠️ Módulo de Alto Risco (Bus Factor crítico):[/bold yellow] Muitas partes do repositório dependem deste arquivo.")
