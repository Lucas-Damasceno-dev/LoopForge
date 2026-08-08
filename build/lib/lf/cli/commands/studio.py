"""Comando CLI 'lf studio' / 'lf ui' para exibir o Terminal Studio TUI do LoopForge v6."""
from __future__ import annotations

import time

import click
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def make_studio_layout() -> Layout:
    """Cria a estrutura de layout em painéis para o LoopForge Terminal Studio."""
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3),
    )
    layout["main"].split_row(
        Layout(name="pipeline_graph", ratio=2),
        Layout(name="live_logs", ratio=3),
    )
    return layout


def build_pipeline_panel(active_node: str = "Developer") -> Panel:
    """Constrói o painel de status do Grafo LangGraph."""
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Agente / Nó", style="bold yellow")
    table.add_column("Papel / Artefato", style="white")
    table.add_column("Status", justify="center")

    nodes = [
        ("CPO", "Épico & Visão", "DONE", "green"),
        ("PM", "User Stories", "DONE", "green"),
        ("Tech Lead", "Tech Spec & Stack", "DONE", "green"),
        ("Developer", "Multi-File Project", "RUNNING", "cyan"),
        ("QA", "Harness Test Suite", "PENDING", "dim"),
        ("AppSec", "Security Review", "PARALLEL", "magenta"),
        ("DevOps", "CI/CD & Deploy", "PARALLEL", "blue"),
    ]

    for name, role, status, color in nodes:
        if name.lower() == active_node.lower():
            badge = f"[bold black on cyan] ➜ {status} [/bold black on cyan]"
        elif status == "DONE":
            badge = f"[bold green]✓ {status}[/bold green]"
        elif status == "PARALLEL":
            badge = f"[magenta]⚡ {status}[/magenta]"
        else:
            badge = f"[dim]{status}[/dim]"
        table.add_row(name, role, badge)

    return Panel(table, title="[bold cyan]⚡ LangGraph DAG Pipeline Status[/bold cyan]", border_style="cyan")


def build_logs_panel(logs: list[str]) -> Panel:
    """Constrói o painel de streaming de logs."""
    text = Text()
    for log in logs[-15:]:
        if "INFO" in log or "sucesso" in log.lower():
            text.append(f"{log}\n", style="green")
        elif "AVISO" in log or "WARN" in log:
            text.append(f"{log}\n", style="yellow")
        elif "ERRO" in log or "FAIL" in log:
            text.append(f"{log}\n", style="bold red")
        else:
            text.append(f"{log}\n", style="cyan")

    return Panel(text, title="[bold magenta]📡 Live Terminal Log Stream[/bold magenta]", border_style="magenta")


@click.command(name="studio")
@click.option("--duration", "-d", type=int, default=10, help="Tempo de exibição da sessão interativa em segundos")
def studio_cmd(duration: int):
    """Inicia o LoopForge Terminal Studio (TUI de monitoramento em tempo real)."""
    layout = make_studio_layout()

    header_panel = Panel(
        "[bold white]🚀 LoopForge v6 Terminal Studio[/bold white] | [cyan]Autonomous Agent Governance[/cyan] | [yellow]Live Session[/yellow]",
        style="on blue",
    )
    footer_panel = Panel(
        "[bold white]Atalhos:[/bold white] [green][R] Run[/green] | [cyan][S] Status[/cyan] | [magenta][E] Export[/magenta] | [red][Q] Sair[/red]",
        border_style="dim",
    )

    layout["header"].update(header_panel)
    layout["footer"].update(footer_panel)

    sample_logs = [
        "[18:45:00] [INFO] Conectando ao orquestrador LangGraph StateGraph...",
        "[18:45:01] [CPO] Épico aprovado com 3 user stories principais.",
        "[18:45:02] [PM] User Stories validadas com critérios de aceite.",
        "[18:45:03] [Tech Lead] Stack 'Python/FastAPI' selecionada autonomamente.",
        "[18:45:04] [Developer] Gerando projeto multi-arquivo (pyproject.toml, main.py, test_main.py)...",
        "[18:45:05] [Memory] 🧠 RAG Memory: 2 lições aprendidas recuperadas do SQLite.",
        "[18:45:06] [Developer] Invocando LLM Engine via OpenCode Subprocess...",
    ]

    nodes_sequence = ["CPO", "PM", "Tech Lead", "Developer", "QA", "AppSec"]

    console.clear()
    start_time = time.time()
    idx = 3

    with Live(layout, refresh_per_second=4, screen=False):
        while time.time() - start_time < duration:
            current_node = nodes_sequence[idx % len(nodes_sequence)]
            layout["main"]["pipeline_graph"].update(build_pipeline_panel(current_node))
            layout["main"]["live_logs"].update(build_logs_panel(sample_logs))

            time.sleep(1.0)
            idx += 1
            sample_logs.append(f"[{time.strftime('%H:%M:%S')}] [{current_node}] Executando ciclo de orquestração do nó...")

    console.print("[bold green]✓ Sessão do Terminal Studio encerrada.[/bold green]")
