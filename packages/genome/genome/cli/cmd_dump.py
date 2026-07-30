"""Subcomando genome dump."""

import click
from genome.core.renderers import render_json, render_markdown, render_summary
from genome.core.scanner import GenomeScanner
from genome.store.sqlite import GenomeStore


@click.command(name="dump")
@click.option("--format", "-f", default="markdown", type=click.Choice(["markdown", "summary", "json"]), help="Formato de saída.")
@click.option("--path", default=".", help="Caminho do repositório.")
def dump_cmd(format: str, path: str):
    """Exibe o genoma do repositório no formato especificado (otimizado para LLMs)."""
    store = GenomeStore(path)
    genome = store.load_genome()
    if not genome:
        scanner = GenomeScanner(path)
        genome = scanner.scan()

    if format == "markdown":
        click.echo(render_markdown(genome))
    elif format == "summary":
        click.echo(render_summary(genome))
    else:
        click.echo(render_json(genome))
