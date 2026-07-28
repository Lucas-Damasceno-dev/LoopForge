import uuid

import click
from rich.console import Console

from lf.config.loader import load_config
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.guardrails.loop_lock import LoopLock
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.recorder import TelemetryRecorder

console = Console()


@click.command(name="run")
@click.option("--mock", is_flag=True, default=False, help="Use mock LLM mode")
@click.option("--interactive", "-i", is_flag=True, default=False,
              help="Pause after key nodes for human approval/adjustment")
def run_cmd(mock: bool, interactive: bool):
    """Execute LoopForge task pipeline."""
    lock = LoopLock()
    session_id = str(uuid.uuid4())[:8]

    if not lock.acquire(session_id):
        console.print("[bold red]Another LoopForge execution is currently active (loop.lock found).[/bold red]")
        return

    try:
        cfg = load_config()
        if not cfg.plan.tasks:
            console.print("[yellow]No tasks in plan. Run `lf plan` first.[/yellow]")
            return

        circuit = CircuitBreaker(max_total_cost=cfg.budget_limit_usd)
        dispatcher = TaskDispatcher(mock_llm=mock, interactive=interactive, circuit_breaker=circuit)
        recorder = TelemetryRecorder()

        console.print(f"[bold green]Starting LoopForge run (Session ID: {session_id})...[/bold green]")
        if interactive:
            console.print("[bold yellow]Interactive mode: pipeline will pause after developer & QA nodes.[/bold yellow]")

        shared_state: dict = {}
        for task in cfg.plan.tasks:
            if not circuit.can_proceed():
                console.print("[bold red]Circuit breaker tripped! Stopping pipeline.[/bold red]")
                break

            console.print(f"\n[bold cyan]Executing Task {task.id}: {task.title}[/bold cyan]")
            try:
                state = dispatcher.dispatch(task, project_id=cfg.project_id, shared_state=shared_state)
                shared_state.update({k: v for k, v in state.items() if v})

                error = state.get("error")
                test_report = state.get("test_report", {})
                has_summary = bool(test_report and "summary" in test_report)
                tests_failed = test_report.get("summary", {}).get("tests_failed", 0) if has_summary else 0

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
                    "done" if (not error and tests_failed == 0) else "failed"
                )
            except Exception as e:
                circuit.record_failure()
                console.print(f"[red]Task {task.id} crashed: {e}[/red]")


    finally:
        lock.release()
