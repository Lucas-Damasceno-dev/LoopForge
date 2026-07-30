"""Subcomando genome init."""

import click
from rich.console import Console
from genome.core.scanner import GenomeScanner

console = Console()


@click.command(name="init")
@click.argument("path", default=".")
@click.option("--incremental", is_flag=True, help="Varredura incremental (apenas modificados).")
def init_cmd(path: str, incremental: bool):
    """Inicializa/atualiza o genoma do repositório."""
    console.print(f"[bold blue]🧬 Gerando genoma do repositório em:[/bold blue] [cyan]{path}[/cyan]...")
    scanner = GenomeScanner(path)
    genome = scanner.scan(incremental=incremental)
    console.print(
        f"[bold green]✓ Genoma gerado com sucesso![/bold green] Total: [yellow]{genome.repo.total_files}[/yellow] arquivos ({genome.repo.total_lines} linhas)."
    )
