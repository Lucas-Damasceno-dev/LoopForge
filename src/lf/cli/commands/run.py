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
@click.option("--mock", is_flag=True, default=True, help="Use mock LLM mode")
def run_cmd(replay: str | None, mock: bool):
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

        dispatcher = TaskDispatcher(mock_llm=mock)
        recorder = TelemetryRecorder()
        circuit = CircuitBreaker(max_total_cost=cfg.budget_limit_usd)
        mock_mode = mock or True

        console.print(f"[bold green]Starting LoopForge run (Session ID: {session_id})...[/bold green]")
        for task in cfg.plan.tasks:
            if not circuit.can_proceed():
                console.print("[bold red]Circuit breaker tripped! Stopping pipeline.[/bold red]")
                break

            console.print(f"\n[bold cyan]Executing Task {task.id}: {task.title}[/bold cyan]")
            try:
                state = dispatcher.dispatch(task, project_id=cfg.project_id)
                error = state.get("error")
                test_report = state.get("test_report", {})
                tests_failed = test_report.get("summary", {}).get("tests_failed", 1) if test_report else 1

                if error:
                    circuit.record_failure()
                    console.print(f"[red]Task {task.id} failed: {error}[/red]")
                elif tests_failed == 0:
                    circuit.record_success()
                    console.print(f"[green]Task {task.id} completed successfully.[/green]")
                else:
                    circuit.record_failure()
                    console.print(f"[red]Task {task.id}: {tests_failed} test(s) failed[/red]")

                recorder.record_node_execution(
                    session_id, task.id, state.get("next_agent", "unknown"),
                    "done" if not error else "failed"
                )
            except Exception as e:
                circuit.record_failure()
                console.print(f"[red]Task {task.id} crashed: {e}[/red]")

    finally:
        lock.release()
