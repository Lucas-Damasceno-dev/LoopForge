import uuid
import click
from rich.console import Console
from lf.config.loader import load_config
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.guardrails.loop_lock import LoopLock
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.recorder import TelemetryRecorder
from lf.telemetry.store import TelemetryStore

console = Console()


@click.command(name="run")
@click.option("--replay", default=None, help="Replay session ID from telemetry")
def run_cmd(replay: str | None):
    """Execute LoopForge task pipeline."""
    lock = LoopLock()
    session_id = replay or str(uuid.uuid4())[:8]

    if not lock.acquire(session_id):
        console.print("[bold red]Another LoopForge execution is currently active (loop.lock found).[/bold red]")
        return

    try:
        if replay:
            console.print(f"[bold yellow]Replaying session {replay}...[/bold yellow]")
            store = TelemetryStore()
            events = store.fetch_all()
            session_events = [e for e in events if e.get("session_id") == replay]
            console.print(f"Found {len(session_events)} historical events for session {replay}.")
            return

        cfg = load_config()
        if not cfg.plan.tasks:
            console.print("[yellow]No tasks in plan. Run `lf plan` first.[/yellow]")
            return

        dispatcher = TaskDispatcher()
        recorder = TelemetryRecorder()
        circuit = CircuitBreaker(budget_limit_usd=cfg.budget_limit_usd)

        console.print(f"[bold green]Starting LoopForge run (Session ID: {session_id})...[/bold green]")
        for task in cfg.plan.tasks:
            if not circuit.can_proceed():
                console.print("[bold red]Circuit breaker tripped! Stopping pipeline.[/bold red]")
                break

            console.print(f"\n[bold cyan]Executing Task {task.id}: {task.title}[/bold cyan]")
            state = dispatcher.dispatch(task, project_id=cfg.project_id)
            status = state.get("status", "done")
            history = state.get("history", [])

            for node_name in history:
                recorder.record_node_execution(session_id, task.id, node_name, status)

            if status == "done":
                circuit.record_success()
                console.print(f"[green]Task {task.id} completed successfully.[/green]")
            else:
                circuit.record_failure()
                console.print(f"[red]Task {task.id} failed: {state.get('error')}[/red]")

    finally:
        lock.release()
