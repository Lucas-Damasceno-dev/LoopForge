"""Subcomando registry check."""

import click
from registry.core.checker import RegistryChecker
from registry.notifier.stdout import StdoutNotifier


@click.command(name="check")
@click.option("--agent", help="Filtrar quebras de contrato que afetam este agente.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def check_cmd(agent: str, repo: str):
    """Verifica se as mudanças de código atuais causaram quebra de contrato de interface."""
    checker = RegistryChecker(repo)
    breaking = checker.check(agent=agent)
    notifier = StdoutNotifier()
    notifier.notify(breaking)
