from pathlib import Path

from lf.config.schema import TaskSchema
from lf.ontology.state_machine.definition import TaskState
from lf.ontology.state_machine.labels import get_git_label
from lf.pipeline.graph import build_graph
from lf.runner.git.checkpoint import GitCheckpointManager
from lf.runner.git.pr import create_github_pr


class TaskDispatcher:
    def __init__(self, mock_llm: bool = True, interactive: bool = False, circuit_breaker=None):
        self.mock_llm = mock_llm
        self.interactive = interactive
        self.circuit_breaker = circuit_breaker
        self._last_graph = None

    def _get_graph(self, checkpointer=None):
        """Retorna grafo compilado (cache por sessão)."""
        return build_graph(
            checkpointer=checkpointer,
            human_gate_enabled=self.interactive,
        )

    def _build_initial_state(self, task: TaskSchema, project_id: str, shared_state: dict | None = None) -> dict:
        target_agent = getattr(task, "agent_id", None) or getattr(task, "persona", None) or "cpo"
        if target_agent not in ("cpo", "pm", "tech_lead", "developer", "qa"):
            target_agent = "cpo"

        ontology = "examples/the-foundry"
        if not Path(ontology).exists():
            repo_ontology = Path(__file__).resolve().parents[3] / "examples" / "the-foundry"
            if repo_ontology.exists():
                ontology = str(repo_ontology)

        state = {
            "idea": task.title,
            "output_dir": f"/tmp/loopforge/{project_id}",
            "epic": {},
            "user_stories": [],
            "tech_spec": "",
            "code": "",
            "test_report": {},
            "ontology_path": ontology,
            "project_dir": ".",
            "stack": "python",
            "next_agent": target_agent,

            "attempt_count": getattr(task, "attempts", 0),
            "max_retries": getattr(task, "max_retries", 3),
            "error": None,
            "feedback_history": [],
            "mock_llm": self.mock_llm,
            "llm_provider": "google",
            "llm_model_name": "gemini-2.0-flash",
            "llm_temperature": 0.3,
            "routing_mode": getattr(task, "routing_mode", "full"),
            "task_type": getattr(task, "task_type", "feature"),
            "is_interactive": self.interactive,
            "expected_schema": None,
            "persona_id": getattr(task, "agent_id", None),
        }



        if shared_state:
            for k, v in shared_state.items():
                if v and k not in ("error", "next_agent"):
                    state[k] = v

        return state


    def _human_interrupt_handler(self, snapshot, config, app) -> bool:
        """Manipula interrupção. Retorna False se o usuário abortou."""
        from rich.console import Console
        console = Console()

        node_name = snapshot.next[0] if snapshot.next else "unknown"
        state = snapshot.values

        console.print(f"\n[bold yellow]⏸️  Pausado após nó: {node_name}[/bold yellow]")

        if node_name == "developer":
            tech_spec = state.get("tech_spec", "")[:300]
            console.print(f"\n[bold]Especificação Técnica (início):[/bold]\n[dim]{tech_spec}...[/dim]")
        elif node_name == "qa":
            report = state.get("test_report", {})
            summary = report.get("summary", {})
            console.print("\n[bold]Relatório de Testes:[/bold]")
            console.print(f"  Total: {summary.get('total_tests', '?')}")
            console.print(f"  Passaram: {summary.get('tests_passed', '?')}")
            console.print(f"  Falharam: {summary.get('tests_failed', '?')}")
            if state.get("error"):
                console.print(f"  [red]Erro: {state['error']}[/red]")

        console.print("\n[bold]Opções:[/bold]")
        console.print("  [green]c[/green] — continuar (aprova este passo)")
        console.print("  [yellow]r[/yellow] — retentar (re-executa o nó)")
        console.print("  [blue]a[/blue] — ajustar prompt (editar e continuar)")
        console.print("  [red]x[/red] — abortar (encerra execução)")

        choice = input("\n➜ ").strip().lower()

        if choice == "x":
            console.print("[red]Execução abortada pelo usuário.[/red]")
            return False
        elif choice == "r":
            # Retentar: reseta erro e re-enfileira o nó atual
            app.update_state(config, {"error": None})
            return True
        elif choice == "a":
            # Ajustar: pede feedback pro usuário e adiciona ao estado
            feedback = input("✏️  Feedback para o agente:\n➜ ")
            app.update_state(config, {
                "error": None,
                "feedback_history": state.get("feedback_history", []) + [
                    {"from": "human", "message": feedback, "node": node_name}
                ],
            })
            return True
        else:
            # Continuar (default)
            console.print("[green]Continuando...[/green]")
            return True

    def _create_pr_with_labels(self, task: TaskSchema, final_state: dict, project_id: str):
        """Cria PR com labels do Foundry ao final da execução."""
        test_report = final_state.get("test_report", {})
        tests_failed = test_report.get("summary", {}).get("tests_failed", 1)
        success = tests_failed == 0 and not final_state.get("error")

        state = TaskState.DONE if success else TaskState.FAILED
        labels = [get_git_label(state)]

        title = f"[LoopForge] {task.title}"
        body = (
            f"## Task: {task.title}\n\n"
            f"**Status:** {state.value}\n"
            f"**Agent:** {task.agent_id}\n"
            f"**Tests Failed:** {tests_failed}\n"
        )

        try:
            GitCheckpointManager().create_checkpoint(f"loopforge/task-{project_id}")
            create_github_pr(title=title, body=body, labels=labels)
        except Exception:
            pass

    def dispatch(self, task: TaskSchema, project_id: str = "project", shared_state: dict | None = None) -> dict:
        import sqlite3
        from pathlib import Path

        from langgraph.checkpoint.sqlite import SqliteSaver

        initial_state = self._build_initial_state(task, project_id, shared_state=shared_state)


        checkpoint_path = str(Path(".loopforge/checkpoints.sqlite").resolve())
        conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        thread_id = f"{project_id}-{task.id}"

        graph = self._get_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        try:
            if self.interactive:
                # --- MODO INTERATIVO: stream + interrupt handling ---
                for event in graph.stream(initial_state, config):
                    for node_name, output in event.items():
                        if isinstance(output, dict) and output.get("status") == "interrupted":
                            pass  # será tratado abaixo

                # Verifica se houve interrupção
                snapshot = graph.get_state(config)
                while snapshot.next:
                    proceed = self._human_interrupt_handler(snapshot, config, graph)
                    if not proceed:
                        break
                    # Resume streaming
                    for event in graph.stream(None, config):
                        pass
                    snapshot = graph.get_state(config)

                state_snapshot = graph.get_state(config)
                result = dict(state_snapshot.values) if state_snapshot.values else {}
            else:
                # --- MODO AUTOMÁTICO: invoke direto ---
                final_state = graph.invoke(initial_state, config)
                result = dict(final_state) if isinstance(final_state, dict) else dict(final_state)

            # Cria PR com labels do Foundry
            self._create_pr_with_labels(task, result, project_id)

            return result

        except Exception as e:
            return {**initial_state, "error": str(e), "status": "failed"}
