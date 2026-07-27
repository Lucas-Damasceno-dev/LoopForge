import json
from pathlib import Path
from rich.console import Console
from rich.table import Table
from lf.telemetry.store import TelemetryStore


def render_analytics_summary(store: TelemetryStore = None):
    store = store or TelemetryStore()
    events = store.fetch_all()

    console = Console()
    table = Table(title="LoopForge Telemetry Runs")

    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Session", style="magenta")
    table.add_column("Task ID", style="green")
    table.add_column("Node", style="yellow")
    table.add_column("Status", style="bold white")
    table.add_column("Duration (s)", justify="right")

    for ev in events[:20]:
        table.add_row(
            str(ev.get("id")),
            str(ev.get("session_id")),
            str(ev.get("task_id")),
            str(ev.get("node")),
            str(ev.get("status")),
            f"{ev.get('duration_seconds', 0.0):.2f}",
        )

    console.print(table)


def export_analytics_json(output_path: str | Path = ".loopforge/analytics.json", store: TelemetryStore = None):
    store = store or TelemetryStore()
    events = store.fetch_all()
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=2), encoding="utf-8")
    return out
