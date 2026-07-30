"""Subcomando registry watch."""

import time
import click
from rich.console import Console
from registry.core.checker import RegistryChecker
from registry.notifier.slack import SlackNotifier
from registry.notifier.stdout import StdoutNotifier

console = Console()


@click.command(name="watch")
@click.option("--notify-webhook", help="Webhook do Slack para envio de alertas de breaking changes.")
@click.option("--interval", default=5, help="Intervalo de polling em segundos.")
@click.option("--repo", default=".", help="Caminho do repositório.")
def watch_cmd(notify_webhook: str, interval: int, repo: str):
    """Monitora o repositório em modo watch e notifica sobre quebras de contrato em tempo real."""
    console.print(f"[bold blue]👀 Iniciando modo Watch do Agentic Registry em:[/bold blue] [cyan]{repo}[/cyan] (intervalo: {interval}s)")
    stdout_notifier = StdoutNotifier()
    slack_notifier = SlackNotifier(notify_webhook) if notify_webhook else None
    checker = RegistryChecker(repo)

    try:
        while True:
            breaking = checker.check()
            if breaking:
                stdout_notifier.notify(breaking)
                if slack_notifier:
                    slack_notifier.notify(breaking)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("[yellow]Watch finalizado pelo usuário.[/yellow]")
