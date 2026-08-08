"""Comando CLI 'lf explore' para navegar interativamente pelo histórico de execuções e decisões humanas."""
import sqlite3
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.command(name="explore")
@click.option("--db-path", default=".loopforge/telemetry.sqlite", help="Caminho do banco SQLite de telemetria")
def explore_cmd(db_path: str):
    """Navega pelo histórico de execuções de pipeline e histórico de decisões humanas (HITL)."""
    db_file = Path(db_path).resolve()
    if not db_file.exists():
        console.print(f"[yellow]Nenhum banco de histórico encontrado em {db_file}. Executando inicialização...[/yellow]")
        return

    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()

    console.print("[bold cyan]🔍 LoopForge Execution & HITL Decision History Explorer[/bold cyan]\n")

    # 1. Pipeline Runs Table
    try:
        cursor.execute("SELECT id, idea, status, stack, duration_seconds, created_at FROM pipeline_runs ORDER BY created_at DESC LIMIT 10")
        runs = cursor.fetchall()
        if runs:
            table_runs = Table(title="🚀 Execuções Recentes de Pipeline (runs)")
            table_runs.add_column("ID", style="dim")
            table_runs.add_column("Ideia / Objetivo", style="bold")
            table_runs.add_column("Status")
            table_runs.add_column("Stack", style="cyan")
            table_runs.add_column("Duração (s)", justify="right", style="yellow")
            table_runs.add_column("Criado em", style="dim")

            for r in runs:
                st = r[2]
                st_fmt = f"[green]{st}[/green]" if st == "done" else f"[red]{st}[/red]" if st == "failed" else f"[yellow]{st}[/yellow]"
                table_runs.add_row(r[0][:8], r[1][:40], st_fmt, r[3], f"{r[4]:.1f}s", str(r[5])[:19])

            console.print(table_runs)
            console.print("")
    except Exception as e:
        console.print(f"[dim]Tabela 'pipeline_runs' vazia ou não criada: {e}[/dim]")

    # 2. Human Decisions Table
    try:
        cursor.execute("SELECT id, run_id, gate_node, action, feedback_category, feedback_message, timestamp FROM human_decisions ORDER BY timestamp DESC LIMIT 10")
        decisions = cursor.fetchall()
        if decisions:
            table_dec = Table(title="👤 Histórico de Decisões Humana (HITL)")
            table_dec.add_column("ID", style="dim")
            table_dec.add_column("Run ID", style="dim")
            table_dec.add_column("Gate Node", style="cyan")
            table_dec.add_column("Ação", style="bold")
            table_dec.add_column("Categoria", style="yellow")
            table_dec.add_column("Mensagem de Feedback")
            table_dec.add_column("Data/Hora", style="dim")

            for d in decisions:
                act = d[3]
                act_fmt = f"[green]{act}[/green]" if act == "approve" else f"[red]{act}[/red]" if act == "abort" else f"[blue]{act}[/blue]"
                table_dec.add_row(d[0][:8], d[1][:8], d[2], act_fmt, str(d[4] or "-"), str(d[5] or "-"), str(d[6])[:19])

            console.print(table_dec)
        else:
            console.print("[dim]Nenhuma decisão humana (HITL) gravada ainda.[/dim]")
    except Exception as e:
        console.print(f"[dim]Histórico de decisões humanas não disponível: {e}[/dim]")

    conn.close()
