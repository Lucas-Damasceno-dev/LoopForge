import sys
import uuid

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from lf.config.loader import load_config
from lf.config.schema import TaskSchema
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.guardrails.loop_lock import LoopLock
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.telemetry.recorder import TelemetryRecorder

console = Console()


def _run_interactive_wizard() -> dict:
    """Wizard interativo disparado ao rodar 'lf run' sem argumentos em TTY."""
    console.print("\n[bold cyan]🧙 Bem-vindo ao Wizard Interativo do LoopForge![/bold cyan]")
    console.print("[dim]Defina os parâmetros do seu pipeline de IA agente em poucos passos.[/dim]\n")

    idea = Prompt.ask("🤖 Qual o objetivo / ideia da funcionalidade?", default="Implementar serviço REST com autenticação")
    stack = Prompt.ask("📦 Stack de tecnologia?", choices=["python", "javascript", "go", "rust"], default="python")
    mode = Prompt.ask("⚡ Modo de roteamento?", choices=["full-path", "fast-path"], default="full-path")
    interactive = Confirm.ask("👤 Ativar revisão humana (HITL) entre os nós?", default=True)
    review_mode = Confirm.ask("🔍 Ativar Modo Revisão (pausa no final antes de salvar em disco)?", default=False)
    notify = Confirm.ask("🔔 Ativar notificações desktop ao pausar/finalizar?", default=False)

    return {
        "idea": idea,
        "stack": stack,
        "mode": mode,
        "interactive": interactive,
        "review_mode": review_mode,
        "notify": notify,
    }


@click.command(name="run")
@click.option("--idea", default=None, help="Ideia ou objetivo da funcionalidade")
@click.option("--stack", default=None, help="Stack de tecnologia (python, java, javascript, go, rust)")
@click.option("--mock", is_flag=True, default=False, help="Usar modo LLM mock")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Pausar após nós para aprovação humana (HITL)")
@click.option("--review-mode", is_flag=True, default=False, help="Modo Revisão: executa tudo e pausa antes de salvar no disco")
@click.option("--notify", is_flag=True, default=False, help="Enviar notificação desktop ao pausar ou finalizar")
@click.option("--webhook-url", default=None, help="URL de Webhook (Slack/Discord) para notificações")
@click.option("--resume", "resume_id", default=None, help="Retomar pipeline interrompida pelo ID da tarefa")
@click.option("--wizard", is_flag=True, default=False, help="Forçar o wizard interativo de inicialização")
def run_cmd(
    idea: str | None,
    stack: str | None,
    mock: bool,
    interactive: bool,
    review_mode: bool,
    notify: bool,
    webhook_url: str | None,
    resume_id: str | None,
    wizard: bool,
):
    """Executa a pipeline de tarefas dos agentes autônomos do LoopForge."""
    lock = LoopLock()
    session_id = str(uuid.uuid4())[:8]

    if not lock.acquire(session_id):
        console.print("[bold red]Outra execução do LoopForge está ativa (loop.lock encontrado).[/bold red]")
        return

    try:
        # 1. Se resume_id for fornecido, executa retomada via checkpoint
        if resume_id:
            dispatcher = TaskDispatcher(mock_llm=mock, interactive=interactive, notify=notify, webhook_url=webhook_url)
            console.print(f"[bold cyan]⚡ Retomando pipeline do checkpoint '{resume_id}'...[/bold cyan]")
            dispatcher.resume(project_id="project", task_id=resume_id)
            return

        # 2. Wizard se não houver ideia/plan ou se --wizard for passado
        if wizard or (not idea and sys.stdin.isatty() and not load_config().plan.tasks):
            wiz = _run_interactive_wizard()
            idea = wiz["idea"]
            stack = wiz["stack"]
            interactive = wiz["interactive"]
            review_mode = wiz["review_mode"]
            notify = wiz["notify"]

        cfg = load_config()
        if stack is None:
            stack = cfg.stack.language if (cfg.stack and cfg.stack.language) else "python"
        circuit = CircuitBreaker(max_total_cost=cfg.budget_limit_usd)
        dispatcher = TaskDispatcher(
            mock_llm=mock,
            interactive=interactive,
            circuit_breaker=circuit,
            review_mode=review_mode,
            notify=notify,
            webhook_url=webhook_url,
        )
        recorder = TelemetryRecorder()

        tasks_to_run = []
        if idea:
            tasks_to_run = [TaskSchema(id="task-1", title=idea, agent_id="cpo", stack=stack)]
        elif cfg.plan.tasks:
            tasks_to_run = cfg.plan.tasks
        else:
            tasks_to_run = [TaskSchema(id="task-1", title="Build application features", agent_id="cpo", stack=stack)]

        console.print(f"[bold green]⚡ Iniciando LoopForge Run (Sessão ID: {session_id})...[/bold green]")
        if interactive:
            console.print("[bold yellow]👤 Modo Interativo (HITL) ativado.[/bold yellow]")
        if review_mode:
            console.print("[bold magenta]🔍 Modo Revisão ativado (pausa no final antes de aplicar).[/bold magenta]")

        shared_state: dict = {}
        for task in tasks_to_run:
            if not circuit.can_proceed():
                console.print("[bold red]Circuit breaker ativado! Interrompendo pipeline.[/bold red]")
                break

            console.print(f"\n[bold cyan]Executando Tarefa {task.id}: {task.title}[/bold cyan]")
            try:
                state = dispatcher.dispatch(task, project_id=cfg.project_id, shared_state=shared_state)
                shared_state.update({k: v for k, v in state.items() if v})

                error = state.get("error")
                test_report = state.get("test_report", {})
                has_summary = bool(test_report and "summary" in test_report)
                tests_failed = test_report.get("summary", {}).get("tests_failed", 0) if has_summary else 0

                if error:
                    circuit.record_failure()
                    console.print(f"[red]Tarefa {task.id} falhou: {error}[/red]")
                elif tests_failed == 0:
                    circuit.record_success()
                    console.print(f"[green]Tarefa {task.id} concluída com sucesso.[/green]")
                else:
                    circuit.record_failure()
                    console.print(f"[red]Tarefa {task.id}: {tests_failed} teste(s) falharam[/red]")

                recorder.record_node_execution(
                    session_id, task.id, state.get("next_agent", "unknown"),
                    "done" if (not error and tests_failed == 0) else "failed"
                )
            except Exception as e:
                circuit.record_failure()
                console.print(f"[red]Tarefa {task.id} falhou com erro: {e}[/red]")

    finally:
        lock.release()
