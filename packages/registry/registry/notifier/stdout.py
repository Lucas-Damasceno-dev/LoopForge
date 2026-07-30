"""Notificador no terminal (stdout) com formatação Rich."""

from typing import List
from rich.console import Console
from registry.notifier.base import BaseNotifier
from registry.store.models import BreakingChange

console = Console()


class StdoutNotifier(BaseNotifier):
    def notify(self, breaking_changes: List[BreakingChange]) -> None:
        if not breaking_changes:
            console.print("[bold green]✓ Nenhum contrato de interface quebrado.[/bold green]")
            return

        console.print(f"[bold red]🚨 BREAKING CHANGE DETECTADA ({len(breaking_changes)}):[/bold red]")
        for bc in breaking_changes:
            console.print(f"  • Interface: [cyan]{bc.interface_name}[/cyan] em [yellow]{bc.module}[/yellow]")
            console.print(f"    - Tipo: {bc.change_type}")
            console.print(f"    - Detalhes: {bc.details}")
            if bc.impacted_consumers:
                console.print("    - Consumidores Afetados:")
                for c in bc.impacted_consumers:
                    console.print(f"      • `{c.file}:{c.line}` (Agente: {c.agent})")
