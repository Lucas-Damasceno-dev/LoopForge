"""Analytics e Relatórios de Custo de Telemetria por Agente/Persona."""
from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from lf.telemetry.store import TelemetryStore

COST_PER_1K_INPUT_TOKENS = 0.00015
COST_PER_1K_OUTPUT_TOKENS = 0.0006


def render_analytics_summary(store: TelemetryStore = None):
    """Exibe painel de métricas e tabela de custos por persona e por nó."""
    store = store or TelemetryStore()
    events = store.fetch_all()

    console = Console()
    table = Table(title="📊 LoopForge Telemetry & Persona Cost Breakdown", header_style="bold cyan")

    table.add_column("Node / Persona", style="bold yellow")
    table.add_column("Execuções", justify="right", style="cyan")
    table.add_column("Tempo Total (s)", justify="right", style="magenta")
    table.add_column("Tokens Est.", justify="right", style="green")
    table.add_column("Custo Est. (USD)", justify="right", style="bold green")

    by_node: dict[str, dict] = {}
    total_cost = 0.0
    total_tokens = 0

    for ev in events:
        node = str(ev.get("node", "unknown")).lower()
        dur = float(ev.get("duration_seconds", 1.2))
        est_tokens = int(dur * 450)  # estimativa por tempo de exec do nó
        est_cost = (est_tokens / 1000.0) * COST_PER_1K_OUTPUT_TOKENS

        if node not in by_node:
            by_node[node] = {"count": 0, "duration": 0.0, "tokens": 0, "cost": 0.0}

        by_node[node]["count"] += 1
        by_node[node]["duration"] += dur
        by_node[node]["tokens"] += est_tokens
        by_node[node]["cost"] += est_cost

        total_cost += est_cost
        total_tokens += est_tokens

    for node, data in by_node.items():
        table.add_row(
            node.upper(),
            str(data["count"]),
            f"{data['duration']:.2f}s",
            f"{data['tokens']:,}",
            f"${data['cost']:.6f}",
        )

    console.print(table)
    console.print(
        Panel(
            f"[bold white]Total de Eventos:[/bold white] {len(events)} | "
            f"[bold green]Tokens Est.:[/bold green] {total_tokens:,} | "
            f"[bold gold1]Custo Total Est.:[/bold gold1] [bold green]${total_cost:.6f} USD[/bold green]",
            title="[bold cyan]Resumo Financeiro da Pipeline[/bold cyan]",
            border_style="green",
        )
    )


def export_analytics_json(output_path: str | Path = ".loopforge/analytics.json", store: TelemetryStore = None):
    """Exporta todas as telemetrias em formato JSON."""
    store = store or TelemetryStore()
    events = store.fetch_all()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=2), encoding="utf-8")
    return out
