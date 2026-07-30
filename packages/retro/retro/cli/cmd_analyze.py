"""Subcomando retro analyze."""

import click
from rich.console import Console
from retro.core.analyzer import SessionAnalyzer
from retro.core.parser import AgDRParser
from retro.core.recommender import Recommender
from retro.report.renderer import RetroRenderer
from retro.store.sqlite import RetroStore

console = Console()


@click.command(name="analyze")
@click.argument("file_path")
@click.option("--repo", default=".", help="Caminho do repositório.")
def analyze_cmd(file_path: str, repo: str):
    """Analisa um arquivo de log de sessão no formato AgDR e gera o relatório retro.md."""
    parser = AgDRParser()
    session = parser.parse_file(file_path)

    analyzer = SessionAnalyzer()
    patterns = analyzer.analyze(session)

    recommender = Recommender()
    learnings = recommender.recommend(session, patterns)

    renderer = RetroRenderer()
    report = renderer.render(session, patterns, learnings)

    store = RetroStore(repo)
    session.patterns = patterns
    session.learnings = learnings
    store.save_session(session)

    console.print(report.summary_md)
