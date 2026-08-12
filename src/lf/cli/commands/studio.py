"""Comando CLI 'lf studio' / 'lf ui' — visualizador de telemetria em tempo real.

Lê o SQLite de telemetria (``.loopforge/telemetry.sqlite``) e exibe as execuções
recentes de pipeline em uma TUI com polling simples. Sem dados fake: se o banco
não existe ou está vazio, os painéis informam isso explicitamente.
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

POLL_INTERVAL_SECONDS = 5.0


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


def fetch_runs(db_path: str, limit: int = 10) -> list[dict[str, Any]]:
    """Lê as execuções recentes do SQLite de telemetria.

    Prefere a tabela ``pipeline_runs`` (writer canônico do task_dispatcher);
    se ausente, tenta a tabela ``runs`` do TelemetryStore. Banco inexistente ou
    sem tabelas retorna lista vazia.
    """
    db_file = Path(db_path).resolve()
    if not db_file.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "pipeline_runs" in tables:
            rows = conn.execute(
                "SELECT id, idea, stack, status, current_node, duration_seconds, created_at "
                "FROM pipeline_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        elif "runs" in tables:
            rows = conn.execute(
                "SELECT id, task_id, node, status, duration_seconds, "
                "timestamp AS created_at FROM runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = []
        conn.close()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _build_stats(runs: list[dict[str, Any]]) -> dict[str, str]:
    """Agrega estatísticas reais das execuções para o painel de resumo."""
    if not runs:
        return {"Execuções": "nenhuma execução encontrada"}

    statuses = [str(r.get("status", "")).lower() for r in runs]
    done = sum(1 for s in statuses if s in ("done", "completed", "success"))
    failed = sum(1 for s in statuses if s == "failed")
    running = sum(1 for s in statuses if s in ("running", "pending"))
    durations = [float(r.get("duration_seconds") or 0.0) for r in runs]
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    last = runs[0]

    return {
        "Execuções (últimas)": str(len(runs)),
        "Concluídas (done)": str(done),
        "Falhas (failed)": str(failed),
        "Em execução/pendente": str(running),
        "Duração média (s)": f"{avg_duration:.1f}",
        "Última execução": (
            f"{str(last.get('id') or '')[:8]} · {last.get('status', '')} · {str(last.get('idea', ''))[:30]}"
        ),
    }


def _run_line(run: dict[str, Any]) -> str:
    """Formata uma execução como linha de log."""
    run_id = str(run.get("id") or "")[:8]
    idea = str(run.get("idea") or run.get("task_id") or "")[:40]
    status = str(run.get("status", ""))
    stack = str(run.get("stack") or run.get("node") or "-")
    duration = float(run.get("duration_seconds") or 0.0)
    created = str(run.get("created_at") or "")[:19]
    return f"[{created}] [{run_id}] {status.upper()} | {idea or '(sem descrição)'} | stack={stack} | {duration:.1f}s"


def build_pipeline_panel(stats: dict[str, str]) -> Panel:
    """Constrói o painel de resumo da telemetria real de execuções."""
    table = Table(show_header=False, expand=True)
    table.add_column("Métrica", style="bold yellow")
    table.add_column("Valor", style="white")

    for key, value in stats.items():
        table.add_row(key, value)

    return Panel(table, title="[bold cyan]📊 Telemetria de Execuções[/bold cyan]", border_style="cyan")


def build_logs_panel(lines: list[str]) -> Panel:
    """Constrói o painel de execuções recentes (stream de logs real)."""
    text = Text()
    if not lines:
        text.append("nenhuma execução encontrada — rode `lf run` para gerar telemetria.\n", style="yellow")
    for line in lines[-15:]:
        if "FAILED" in line:
            text.append(f"{line}\n", style="bold red")
        elif "DONE" in line or "COMPLETED" in line or "SUCCESS" in line:
            text.append(f"{line}\n", style="green")
        elif "RUNNING" in line or "PENDING" in line:
            text.append(f"{line}\n", style="cyan")
        else:
            text.append(f"{line}\n", style="yellow")

    return Panel(text, title="[bold magenta]📡 Execuções Recentes (telemetria)[/bold magenta]", border_style="magenta")


def _read_key() -> str | None:
    """Lê uma tecla do stdin sem bloquear (retorna None fora de terminal)."""
    if not sys.stdin.isatty():
        return None
    try:
        import select

        if select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            return sys.stdin.read(1).lower()
    except Exception:
        return None
    return None


@click.command(name="studio")
@click.option(
    "--duration", "-d", type=int, default=10, help="Tempo máximo da sessão em segundos (0 = até pressionar Q)"
)
@click.option("--db-path", default=".loopforge/telemetry.sqlite", help="Caminho do SQLite de telemetria")
def studio_cmd(duration: int, db_path: str):
    """Visualiza a telemetria real das execuções de pipeline (SQLite) em tempo real."""
    layout = make_studio_layout()

    header_panel = Panel(
        "[bold white]🚀 LoopForge Terminal Studio[/bold white] | [cyan]Visualizador de Telemetria[/cyan] | "
        f"[yellow]DB: {db_path}[/yellow]",
        style="on blue",
    )
    footer_panel = Panel(
        "[bold white]Atalhos:[/bold white] [green][R] Refresh[/green] (relê o DB) | [red][Q] Sair[/red]",
        border_style="dim",
    )

    layout["header"].update(header_panel)
    layout["footer"].update(footer_panel)

    runs = fetch_runs(db_path)
    layout["main"]["pipeline_graph"].update(build_pipeline_panel(_build_stats(runs)))
    layout["main"]["live_logs"].update(build_logs_panel([_run_line(r) for r in runs]))

    console.clear()
    start_time = time.time()
    last_refresh = start_time

    with Live(layout, refresh_per_second=4, screen=False):
        while True:
            if duration > 0 and time.time() - start_time >= duration:
                break
            key = _read_key()
            if key == "q":
                break
            now = time.time()
            if key == "r" or now - last_refresh >= POLL_INTERVAL_SECONDS:
                runs = fetch_runs(db_path)
                layout["main"]["pipeline_graph"].update(build_pipeline_panel(_build_stats(runs)))
                layout["main"]["live_logs"].update(build_logs_panel([_run_line(r) for r in runs]))
                last_refresh = now
            time.sleep(0.25)

    console.print("[bold green]✓ Sessão do Terminal Studio encerrada.[/bold green]")
