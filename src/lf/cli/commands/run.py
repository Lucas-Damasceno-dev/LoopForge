import sys
import time
import uuid
from typing import Literal

import click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from lf.cli.commands.pr import create_git_pr
from lf.config.loader import load_config
from lf.config.schema import TaskSchema
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.orchestrator.task_dispatcher import TaskDispatcher

console = Console()


def _run_interactive_wizard() -> dict:
    """Wizard interativo disparado ao rodar 'lf run' sem argumentos em TTY."""
    console.print("\n[bold cyan]🧙 Bem-vindo ao Wizard Interativo do LoopForge![/bold cyan]")
    console.print("[dim]Defina os parâmetros do seu pipeline de IA agente em poucos passos.[/dim]\n")

    idea = Prompt.ask(
        "🤖 Qual o objetivo / ideia da funcionalidade?", default="Implementar serviço REST com autenticação"
    )
    stack = Prompt.ask(
        "📦 Stack de tecnologia (opcional, Pressione Enter para deixar o Tech Lead decidir)?", default=""
    )
    mode = Prompt.ask("⚡ Modo de roteamento?", choices=["full-path", "fast-path"], default="full-path")
    interactive = Confirm.ask("👤 Ativar revisão humana (HITL) entre os nós?", default=True)
    review_mode = Confirm.ask("🔍 Ativar Modo Revisão (pausa no final antes de salvar em disco)?", default=False)
    notify = Confirm.ask("🔔 Ativar notificações desktop ao pausar/finalizar?", default=False)

    return {
        "idea": idea,
        "stack": stack if stack else None,
        "mode": mode,
        "interactive": interactive,
        "review_mode": review_mode,
        "notify": notify,
    }


def _build_wizard_task_schema(
    idea: str,
    stack: str | None = None,
    complexity: Literal["mvp", "standard", "advanced"] = "standard",
    interactive: bool = False,
) -> TaskSchema:
    """Constrói o objeto TaskSchema a partir dos parâmetros coletados no wizard ou CLI."""
    return TaskSchema(
        id=f"task-{int(time.time())}",
        title=idea,
        stack=stack or "python",
        complexity_level=complexity,
    )


def _print_cost_report(session_id: str, watermark: int | None, retries_consumed: int, circuit: CircuitBreaker) -> None:
    """Imprime relatório de custo real por nó, cache hit rate e retries (A5).

    Custo real vem de ``llm_costs`` (telemetry.sqlite) via watermark — apenas
    as chamadas LLM desta run. Sem custo medido, reporta "n/a" (nunca hardcode).
    Persiste os custos por nó na tabela ``runs`` do TelemetryStore (schema
    permite: session_id, task_id, node, status, cost_usd).
    """
    from rich.table import Table

    from lf.pipeline.cache import SQLiteLLMCache
    from lf.telemetry.costs import query_llm_costs_since, query_node_costs_since
    from lf.telemetry.store import TelemetryStore

    node_costs = query_node_costs_since(watermark)
    total = query_llm_costs_since(watermark)

    table = Table(title="💰 Relatório de Custo (USD) por Nó do Pipeline")
    table.add_column("Nó", style="cyan")
    table.add_column("Custo (USD)", justify="right", style="yellow")
    if node_costs:
        for node, cost in node_costs.items():
            table.add_row(node, f"${cost:.6f}")
    else:
        table.add_row("(nenhum custo medido)", "n/a")
    console.print(table)

    cache_stats = SQLiteLLMCache().stats()
    console.print(
        f"\n🗄️ [bold]Cache LLM:[/bold] {cache_stats['hits']} hits, "
        f"{cache_stats['misses']} misses, "
        f"hit rate {cache_stats['hit_rate'] * 100:.1f}% "
        f"({cache_stats['total']} consultas)"
    )
    console.print(
        f"🔁 [bold]Retries consumidos:[/bold] {retries_consumed} "
        f"(iterações do circuit breaker: {circuit.total_iterations})"
    )
    total_str = f"${total['total_cost_usd']:.6f}" if total["available"] else "n/a"
    console.print(f"💰 [bold]Custo total da run ({session_id}):[/bold] {total_str}")

    # Persiste custos por nó no TelemetryStore (schema de runs aceita cost_usd)
    store = TelemetryStore()
    for node, cost in node_costs.items():
        store.log_event(session_id=session_id, task_id=f"task-{node}", node=node, status="done", cost=cost)


@click.command(name="run")
@click.option("--idea", default=None, help="Ideia ou objetivo da funcionalidade")
@click.option("--stack", default=None, help="Stack de tecnologia opcional (se omitido, o Tech Lead decide)")
@click.option("--pr", is_flag=True, default=False, help="Criar commit e Pull Request no GitHub após a conclusão")
@click.option("--mock", is_flag=True, default=False, help="Usar modo LLM mock")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Pausar após nós para aprovação humana (HITL)")
@click.option(
    "--review-mode", is_flag=True, default=False, help="Modo Revisão: executa tudo e pausa antes de salvar no disco"
)
@click.option("--notify", is_flag=True, default=False, help="Enviar notificação desktop ao pausar ou finalizar")
@click.option("--webhook-url", default=None, help="URL de Webhook (Slack/Discord) para notificações")
@click.option("--resume", "resume_id", default=None, help="Retomar pipeline interrompida pelo ID da tarefa")
@click.option(
    "--mvp", is_flag=True, default=False, help="Modo MVP: escopo enxuto, prototipagem rápida e requisitos essenciais"
)
@click.option(
    "--advanced",
    is_flag=True,
    default=False,
    help="Modo Avançado: escopo completo, múltiplos módulos e alta complexidade",
)
@click.option("--wizard", is_flag=True, default=False, help="Forçar o wizard interativo de inicialização")
@click.option(
    "--report-cost",
    is_flag=True,
    default=False,
    help="Imprimir relatório de custo real por nó, cache hit rate e retries consumidos",
)
@click.option(
    "--sandbox/--no-sandbox",
    default=None,
    help="Executar em Git Worktree isolada (.slim/worktrees/) com merge seguro",
)
def run_cmd(
    idea: str | None,
    stack: str | None,
    pr: bool,
    mock: bool,
    interactive: bool,
    review_mode: bool,
    notify: bool,
    webhook_url: str | None,
    resume_id: str | None,
    mvp: bool,
    advanced: bool,
    wizard: bool,
    report_cost: bool,
    sandbox: bool | None,
):
    """Executa a pipeline de tarefas dos agentes autônomos do LoopForge."""
    session_id = str(uuid.uuid4())[:8]
    complexity_level: Literal["mvp", "standard", "advanced"] = (
        "mvp" if mvp else ("advanced" if advanced else "standard")
    )

    if resume_id:
        cfg = load_config()
        project_id = getattr(cfg, "project_id", None) or "project"
        dispatcher = TaskDispatcher(
            mock_llm=mock,
            interactive=interactive,
            notify=notify,
            webhook_url=webhook_url,
            sandbox_enabled=sandbox,
        )
        console.print(f"[bold cyan]⚡ Retomando pipeline do checkpoint '{resume_id}'...[/bold cyan]")
        dispatcher.resume(project_id=project_id, task_id=resume_id)
        return

    if wizard or (not idea and sys.stdin.isatty() and not load_config().plan.tasks):
        wiz = _run_interactive_wizard()
        idea = wiz["idea"]
        stack = wiz["stack"]
        interactive = wiz["interactive"]
        review_mode = wiz["review_mode"]
        notify = wiz["notify"]

    cfg = load_config()
    circuit = CircuitBreaker(max_total_cost=cfg.budget_limit_usd)
    # A5: watermark do custo real (llm_costs) ANTES da run — isola as chamadas
    # LLM desta sessão das anteriores para o relatório de custo por nó.
    from lf.telemetry.costs import snapshot_llm_cost_watermark

    watermark = snapshot_llm_cost_watermark()
    retries_consumed = 0
    dispatcher = TaskDispatcher(
        mock_llm=mock,
        interactive=interactive,
        circuit_breaker=circuit,
        review_mode=review_mode,
        notify=notify,
        webhook_url=webhook_url,
        sandbox_enabled=sandbox,
    )

    tasks_to_run = []
    if idea:
        tasks_to_run = [
            TaskSchema(id="task-1", title=idea, agent_id="cpo", stack=stack, complexity_level=complexity_level)
        ]
    elif cfg.plan.tasks:
        tasks_to_run = cfg.plan.tasks
    else:
        tasks_to_run = [
            TaskSchema(
                id="task-1",
                title="Build application features",
                agent_id="cpo",
                stack=stack,
                complexity_level=complexity_level,
            )
        ]

    console.print(f"[bold green]⚡ Iniciando LoopForge Run (Sessão ID: {session_id})...[/bold green]")
    if complexity_level != "standard":
        console.print(f"[bold magenta]🎯 Nível de Complexidade: {complexity_level.upper()}[/bold magenta]")
    if stack:
        console.print(f"[dim]📌 Override de Stack manual do usuário: {stack}[/dim]")
    else:
        console.print("[dim]📌 Stack tecnológica será definida autonomamente pelo Tech Lead.[/dim]")

    if interactive:
        console.print("[bold yellow]👤 Modo Interativo (HITL) ativado.[/bold yellow]")

    shared_state: dict = {}
    last_output_dir = "."

    for task in tasks_to_run:
        if not circuit.can_proceed():
            console.print("[bold red]Circuit breaker ativado! Interrompendo pipeline.[/bold red]")
            break

        console.print(f"\n[bold cyan]Executando Tarefa {task.id}: {task.title}[/bold cyan]")
        try:
            state = dispatcher.dispatch(task, project_id=cfg.project_id, shared_state=shared_state)
            shared_state.update({k: v for k, v in state.items() if v})
            # A5: retries consumidos = tentativas de nó (attempt/qa) acumuladas
            retries_consumed += int(state.get("attempt_count", 0) or 0)
            retries_consumed += int(state.get("qa_attempt_count", 0) or 0)

            last_output_dir = state.get("output_dir", last_output_dir)
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
        except Exception as e:
            circuit.record_failure()
            console.print(f"[red]Tarefa {task.id} falhou com erro: {e}[/red]")

    # A5: relatório de custo real por feature (--report-cost)
    if report_cost:
        _print_cost_report(
            session_id=session_id,
            watermark=watermark,
            retries_consumed=retries_consumed,
            circuit=circuit,
        )

    # Se a flag --pr foi passada, dispara a criação de commit e PR no git
    if pr:
        console.print(f"\n[bold cyan]🐙 Criando commit e PR no GitHub para a sessão {session_id}...[/bold cyan]")
        pr_res = create_git_pr(project_dir=last_output_dir, idea=idea or "LoopForge Feature", session_id=session_id)
        if pr_res["status"] == "success":
            console.print(f"[bold green]✔ Commit criado:[/bold green] {pr_res['commit_msg']}")
            if pr_res.get("pr_url"):
                console.print(f"[bold gold1]🔗 PR criado:[/bold gold1] {pr_res['pr_url']}")
        else:
            console.print(f"[bold red]✖ Erro ao criar PR:[/bold red] {pr_res.get('message')}")
