import asyncio
import contextlib
import json
import logging
import os
import select
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from lf.api.websocket_manager import ws_manager
from lf.config.schema import TaskSchema
from lf.ontology.state_machine.definition import TaskState
from lf.ontology.state_machine.labels import get_git_label
from lf.pipeline.graph import build_graph
from lf.runner.git.checkpoint import GitCheckpointManager
from lf.runner.git.pr import create_github_pr

logger = logging.getLogger(__name__)


def _send_notification(title: str, message: str, webhook_url: str | None = None):
    """Envia notificação desktop e/ou webhook para Slack/Discord."""
    with contextlib.suppress(Exception):
        print("\a", end="", flush=True)

    if shutil.which("notify-send"):
        with contextlib.suppress(Exception):
            subprocess.run(["notify-send", title, message], timeout=3, check=False)

    if webhook_url:
        try:
            import urllib.request
            payload = json.dumps({"text": f"*{title}*\n{message}"}).encode("utf-8")
            req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=3)
        except Exception as exc:
            logger.warning("Falha ao enviar notificação webhook: %s", exc)


class TaskDispatcher:
    def __init__(
        self,
        mock_llm: bool = True,
        interactive: bool = False,
        circuit_breaker=None,
        review_mode: bool = False,
        notify: bool = False,
        webhook_url: str | None = None,
        hitl_timeout_seconds: int = 300,
    ):
        self.mock_llm = mock_llm
        self.interactive = interactive
        self.circuit_breaker = circuit_breaker
        self.review_mode = review_mode
        self.notify = notify
        self.webhook_url = webhook_url
        self.hitl_timeout_seconds = hitl_timeout_seconds
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
            "stack": getattr(task, "stack", None),
            "next_agent": target_agent,

            "attempt_count": getattr(task, "attempts", 0),
            "qa_attempt_count": 0,
            "appsec_attempt_count": 0,
            "max_retries": getattr(task, "max_retries", 3),
            "error": None,
            "feedback_history": [],
            "mock_llm": self.mock_llm,
            "llm_provider": "openrouter" if os.getenv("OPENROUTER_API_KEY") else "google",
            "llm_model_name": os.getenv("OPENROUTER_MODEL") or os.getenv("OPENCODE_MODEL") or ("inclusionai/ling-3.0-flash:free" if os.getenv("OPENROUTER_API_KEY") else "gemini-2.0-flash"),
            "llm_temperature": 0.3,

            "routing_mode": getattr(task, "routing_mode", "full"),
            "task_type": getattr(task, "task_type", "feature"),
            "complexity_level": getattr(task, "complexity_level", "standard"),
            "is_interactive": self.interactive,
            "expected_schema": None,
            "persona_id": getattr(task, "agent_id", None),
        }

        if shared_state:
            for k, v in shared_state.items():
                if v and k not in ("error", "next_agent"):
                    state[k] = v

        return state

    def _broadcast_ws(self, event_type: str, task_id: str, payload: dict):
        """Emite evento via WebSocket manager para conectividade em tempo real."""
        try:
            message = {
                "event": event_type,
                "task_id": task_id,
                "timestamp": datetime.now(UTC).isoformat(),
                **payload,
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast(message))
            except RuntimeError:
                asyncio.run(ws_manager.broadcast(message))
        except Exception as exc:
            logger.warning("Falha ao transmitir evento WS: %s", exc)

    def _get_input_with_timeout(self, prompt_text: str, timeout: int = 300) -> str:
        """Lê input com suporte a timeout no Unix/Linux."""
        print(prompt_text, end="", flush=True)
        try:
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                return sys.stdin.readline().strip()
            else:
                print(f"\n[TIMEOUT] Nenhuma resposta recebida em {timeout}s.")
                return ""
        except Exception:
            try:
                return input()
            except Exception:
                # Fallback consistente com o timeout Unix (aborta em vez de aprovar)
                return "x"



    def _check_remote_decision(self, run_id: str, timeout: int = 300) -> dict | None:
        """Poll por decisão remota via API com timeout.

        Verifica a cada 2s se há decisão gravada na tabela human_decisions
        (escrita pelo endpoint POST /api/runs/{run_id}/decide).
        Retorna a decisão assim que disponível, ou None se o timeout expirar.
        """
        if not run_id or run_id in ("default-run", "test", "test-run", "test-thread"):
            return None

        db_path = Path(".loopforge/telemetry.sqlite").resolve()
        if not db_path.exists():
            return None

        console = Console()
        deadline = time.monotonic() + timeout
        last_checked: float = 0.0
        poll_interval = 2.0

        while time.monotonic() < deadline:
            # Evita polling excessivo na mesma fração de segundo
            now = time.monotonic()
            if now - last_checked < poll_interval:
                time.sleep(0.2)
                continue
            last_checked = now

            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT action, feedback_category, feedback_message FROM human_decisions WHERE run_id = ? ORDER BY timestamp DESC LIMIT 1",
                    (run_id,),
                )
                row = cursor.fetchone()
                conn.close()
                if row:
                    console.print(f"[bold green]➜ Decisão Remota via API Detectada: {row[0].upper()}[/bold green]")
                    return {"action": row[0], "category": row[1], "message": row[2]}
            except Exception as exc:
                logger.warning("Falha ao verificar decisão remota: %s", exc)

            remaining = int(deadline - time.monotonic())
            if remaining > 0 and remaining % 10 == 0:
                console.print(f"[dim]⏳ Aguardando decisão remota... ({remaining}s restantes)[/dim]")

        console.print("[dim]⏳ Tempo de espera por decisão remota expirou. Usando input local.[/dim]")
        return None

    def _record_decision(
        self,
        run_id: str,
        gate_node: str,
        action: str,
        category: str | None = None,
        message: str | None = None,
    ):
        """Salva histórico de decisões humanas no SQLite."""
        try:
            db_path = Path(".loopforge/telemetry.sqlite").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS human_decisions (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    gate_node TEXT NOT NULL,
                    action TEXT NOT NULL,
                    feedback_category TEXT,
                    feedback_message TEXT,
                    user TEXT DEFAULT 'human_operator',
                    timestamp TEXT NOT NULL
                )
            """)
            decision_id = str(uuid.uuid4())
            now_iso = datetime.now(UTC).isoformat()
            cursor.execute(
                "INSERT INTO human_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (decision_id, run_id, gate_node, action, category, message, "human_operator", now_iso),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"--- AVISO: Falha ao gravar decisão humana: {e} ---")

    def _human_interrupt_handler(self, snapshot, config, app) -> bool:
        """Manipula interrupção humana (HITL) exibindo os artefatos do nó RECÉM-CONCLUÍDO e o gate do PRÓXIMO nó."""
        console = Console()
        next_node = snapshot.next[0] if snapshot.next else "unknown"
        node_name = next_node
        state = snapshot.values

        run_id = config.get("configurable", {}).get("thread_id", "default-run")

        if self.notify:
            title = f"⏸️ Pipeline Pausado — Gate antes de {next_node.upper()}"
            msg_text = f"LoopForge aguardando aprovação humana antes de executar o nó {next_node}."
            _send_notification(title, msg_text, webhook_url=self.webhook_url)

        console.print("\n[bold yellow]═══════════════════════════════════════════════════════════════════[/bold yellow]")
        console.print(f"[bold yellow]⏸️  HUMAN-IN-THE-LOOP GATE — Próximo Nó: [bold white]{next_node.upper()}[/bold white][/bold yellow]")
        console.print("[bold yellow]═══════════════════════════════════════════════════════════════════[/bold yellow]\n")

        # 1. Se estamos pausados antes de QA, o nó que recém-executou foi o DEVELOPER -> mostra o código gerado
        if next_node == "qa":
            code = state.get("code", "")
            console.print("[bold cyan]📝 Código Gerado pelo Developer (preview):[/bold cyan]")
            if any(err_kw in code for err_kw in ["Model not found", "UnknownError", "Error:", "xdotool:"]):
                console.print()
                console.print("[bold red]┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓[/bold red]")
                console.print("[bold red]┃ ⚠️  ERRO: A saída do Developer contém ERRO do LLM/ferramenta[/bold red]")
                console.print("[bold red]┃    Não é código válido. Revise antes de aprovar.           [/bold red]")
                console.print("[bold red]┃    Sugestão: digite [yellow]r[/yellow] para retentar ou [yellow]a[/yellow] para ajustar o prompt.[/bold red]")
                console.print("[bold red]┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛[/bold red]")
                console.print()

            if code:
                import re
                clean_code = re.sub(r'\x1b\[[0-9;]*m', '', str(code)[:600])
                try:
                    syntax = Syntax(clean_code + ("..." if len(code) > 600 else ""), "python", theme="monokai", line_numbers=True)
                    console.print(syntax)
                except Exception:
                    console.print(clean_code)
            else:
                console.print("[dim]Nenhum código gerado.[/dim]")


        # 2. Se estamos pausados antes do DEVELOPER, mostra a especificação do TECH LEAD
        elif next_node == "developer":
            tech_spec = state.get("tech_spec", "")
            console.print("[bold cyan]📋 Especificação Técnica do Tech Lead (preview):[/bold cyan]")
            if tech_spec:
                console.print(f"[dim]{tech_spec[:500]}...[/dim]")
            else:
                console.print("[dim]Nenhuma especificação disponível.[/dim]")

        # 3. Se estamos pausados antes do APPSEC, mostra o relatório de testes do QA
        elif next_node == "appsec":
            report = state.get("test_report", {})
            summary = report.get("summary", {})
            table = Table(title="🧪 Relatório de Testes Executados (QA)")
            table.add_column("Total", justify="right")
            table.add_column("Passaram", justify="right", style="green")
            table.add_column("Falharam", justify="right", style="red")
            table.add_column("Duração (s)", justify="right", style="yellow")
            table.add_row(
                str(summary.get("total_tests", 0)),
                str(summary.get("tests_passed", 0)),
                str(summary.get("tests_failed", 0)),
                f"{summary.get('duration_seconds', 0.0):.2f}s",
            )
            console.print(table)

        # 4. Se estamos pausados antes do DEVOPS, mostra a revisão do APPSEC
        elif next_node == "devops":
            sec_review = state.get("security_review", {})
            vulns = sec_review.get("vulnerabilities", [])
            table = Table(title="🛡️ Auditoria de Segurança (AppSec)")
            table.add_column("ID", style="dim")
            table.add_column("Severidade")
            table.add_column("Regra", style="cyan")
            table.add_column("Descrição")

            for v in vulns:
                sev = str(v.get("severity", "Low")).upper()
                if sev == "CRITICAL":
                    sev_fmt = f"[bold red]{sev}[/bold red]"
                elif sev == "HIGH":
                    sev_fmt = f"[bold magenta]{sev}[/bold magenta]"
                elif sev == "MEDIUM":
                    sev_fmt = f"[yellow]{sev}[/yellow]"
                else:
                    sev_fmt = f"[cyan]{sev}[/cyan]"
                table.add_row(str(v.get("id", "-")), sev_fmt, str(v.get("rule_id", "-")), str(v.get("description", "-")))
            console.print(table)

        # 5. Se estamos pausados antes do PARALLEL AUDIT, mostra resumo da auditoria final
        elif next_node == "parallel_audit":
            sec_review = state.get("security_review", {})
            ops_report = state.get("devops_report", {})
            vulns = sec_review.get("vulnerabilities", [])
            console.print("[bold magenta]🔎 Auditoria Final (AppSec + DevOps):[/bold magenta]")
            table = Table(title="🛡️ Vulnerabilidades (AppSec)")
            table.add_column("ID", style="dim")
            table.add_column("Severidade")
            table.add_column("Descrição")
            for v in vulns:
                sev = str(v.get("severity", "Low")).upper()
                sev_fmt = f"[bold red]{sev}[/bold red]" if sev == "CRITICAL" else f"[yellow]{sev}[/yellow]"
                table.add_row(str(v.get("id", "-")), sev_fmt, str(v.get("description", "-")))
            console.print(table)
            deployable = ops_report.get("deployable") or ops_report.get("status")
            console.print(f"[cyan]Deployabilidade (DevOps):[/cyan] {deployable if deployable else ops_report}")

        console.print("\n[bold]Ações Disponíveis:[/bold]")
        console.print("  [green]c[/green] — Continuar / Aprovar")
        console.print("  [yellow]r[/yellow] — Retentar nó anterior")
        console.print("  [blue]a[/blue] — Solicitar alterações / Ajustar Prompt (Request Changes)")
        console.print("  [red]x[/red] — Abortar pipeline")

        console.print(f"\n[dim]Tempo limite para resposta: {self.hitl_timeout_seconds}s (Padrão ao esgotar tempo: ABORTAR)[/dim]")
        remote_decision = self._check_remote_decision(run_id, timeout=self.hitl_timeout_seconds)
        if remote_decision:
            choice_map = {"approve": "c", "retry": "r", "adjust_prompt": "a", "abort": "x"}
            choice = choice_map.get(remote_decision["action"], "c")
            console.print(f"[bold green]➜ Decisão Remota via API Detectada: {remote_decision['action'].upper()}[/bold green]")
        else:
            raw_choice = self._get_input_with_timeout("➜ Escolha [c/r/a/x] (default: x): ", timeout=self.hitl_timeout_seconds)
            choice = raw_choice.strip().lower() if raw_choice else "x"

        action = "approve"
        cat = None
        msg = None



        if choice == "x":
            action = "abort"
            console.print("[red]Pipeline abortado pelo operador humano.[/red]")
            self._record_decision(run_id, node_name, action, cat, msg)
            return False

        elif choice == "r":
            action = "retry"
            app.update_state(config, {"error": None})
            self._record_decision(run_id, node_name, action, cat, msg)
            return True

        elif choice == "a":
            action = "adjust_prompt"
            console.print("\n[bold cyan]✏️  Feedback Estruturado (Request Changes):[/bold cyan]")
            console.print("  Categoria: [1] Bug  [2] Style  [3] Missing Feature  [4] General")
            cat_choice = self._get_input_with_timeout("➜ Categoria [1-4] (default: 4): ", timeout=60) or "4"
            cat_map = {"1": "bug", "2": "style", "3": "missing_feature", "4": "general"}
            cat = cat_map.get(cat_choice.strip(), "general")

            msg = self._get_input_with_timeout("➜ Mensagem detalhada de feedback: ", timeout=120) or "Ajustar implementação."

            app.update_state(config, {
                "error": None,
                "feedback_history": state.get("feedback_history", []) + [
                    {
                        "from": "human",
                        "node": node_name,
                        "category": cat,
                        "message": msg,
                    }
                ],
            })
            self._record_decision(run_id, node_name, action, cat, msg)
            return True

        else:
            action = "approve"
            console.print("[bold green]✅ Passo Aprovado. Continuando...[/bold green]")
            self._record_decision(run_id, node_name, action, cat, msg)
            return True

    def _review_mode_approval_gate(self, final_state: dict) -> bool:
        """Modo Revisão: Exibe o plano/artefatos completos e solicita aprovação final antes de escrever em disco."""
        console = Console()
        console.print("\n[bold magenta]═══════════════════════════════════════════════════════════════════[/bold magenta]")
        console.print("[bold magenta]🔍 MODO REVISÃO INTERATIVA — APROVAÇÃO DE MUDANÇAS[/bold magenta]")
        console.print("[bold magenta]═══════════════════════════════════════════════════════════════════[/bold magenta]\n")

        console.print(f"[bold]Ideia / Objetivo:[/bold] {final_state.get('idea')}")
        console.print(f"[bold]Épico CPO:[/bold] {final_state.get('epic', {}).get('title', 'N/A')}")
        console.print(f"[bold]User Stories PM:[/bold] {len(final_state.get('user_stories', []))} estória(s)")
        console.print(f"[bold]Tech Spec Tech Lead:[/bold] {final_state.get('tech_spec', '')[:150]}...")
        console.print(f"[bold]DevOps Score:[/bold] {final_state.get('devops_review', {}).get('deployability_score', 100.0)}/100")

        console.print("\n[bold yellow]Deseja aplicar todas as mudanças propostas no disco?[/bold yellow]")
        choice = self._get_input_with_timeout("➜ Aplicar alterações? [s/N]: ", timeout=120).strip().lower()

        if choice in ("s", "sim", "y", "yes"):
            console.print("[bold green]✅ Mudanças Aprovadas! Aplicando no projeto...[/bold green]")
            return True
        else:
            console.print("[bold yellow]⚠️  Mudanças descartadas no modo revisão.[/bold yellow]")
            return False

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
        except Exception as e:
            print(f"--- AVISO: Falha ao criar checkpoint/PR: {e} ---")

    def list_checkpoints(self) -> list[str]:
        """Lista todos os thread_ids com checkpoints gravados em .loopforge/checkpoints.sqlite."""
        checkpoint_path = str(Path(".loopforge/checkpoints.sqlite").resolve())
        if not Path(checkpoint_path).exists():
            return []

        conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints")
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            print(f"--- AVISO: Falha ao listar checkpoints: {e} ---")
            return []
        finally:
            conn.close()

    def dispatch(self, task: TaskSchema, project_id: str = "project", shared_state: dict | None = None) -> dict:
        initial_state = self._build_initial_state(task, project_id, shared_state=shared_state)

        checkpoint_path = Path(".loopforge/checkpoints.sqlite").resolve()
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        thread_id = f"{project_id}-{task.id}"

        graph = self._get_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}

        self._broadcast_ws("pipeline_started", task.id, {"idea": task.title, "node": initial_state.get("next_agent")})

        try:
            for event in graph.stream(initial_state, config):
                for node_name, output in event.items():
                    if isinstance(output, dict):
                        next_agent = output.get("next_agent")
                        self._broadcast_ws("node_execution", task.id, {
                            "node": node_name,
                            "next_agent": next_agent,
                            "attempt_count": output.get("attempt_count", 0),
                        })

            if self.interactive:
                snapshot = graph.get_state(config)
                while snapshot.next:
                    proceed = self._human_interrupt_handler(snapshot, config, graph)
                    if not proceed:
                        break
                    for event in graph.stream(None, config):
                        for node_name, output in event.items():
                            if isinstance(output, dict):
                                self._broadcast_ws("node_execution", task.id, {
                                    "node": node_name,
                                    "next_agent": output.get("next_agent"),
                                })
                    snapshot = graph.get_state(config)

            state_snapshot = graph.get_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            if self.review_mode:
                approved = self._review_mode_approval_gate(result)
                if not approved:
                    result["error"] = "Review mode rejected by user"

            final_status = "completed" if not result.get("error") else "failed"
            final_event = "pipeline_finished" if final_status == "completed" else "pipeline_failed"
            self._broadcast_ws(final_event, task.id, {
                "status": final_status,
                "error": result.get("error"),
            })

            if self.notify:
                status_label = "Concluído com Sucesso!" if not result.get("error") else "Falhou."
                _send_notification("🚀 Pipeline Finalizado", f"Task {task.id}: {status_label}", webhook_url=self.webhook_url)

            self._create_pr_with_labels(task, result, project_id)
            return result

        except Exception as e:
            self._broadcast_ws("pipeline_error", task.id, {"error": str(e)})
            return {**initial_state, "error": str(e), "status": "failed"}

    def resume(self, project_id: str = "project", task_id: str = "task-1") -> dict:
        """Retoma a execução de uma pipeline a partir do último nó bem-sucedido via SqliteSaver checkpoint."""
        checkpoint_path = Path(".loopforge/checkpoints.sqlite").resolve()
        if not checkpoint_path.exists():
            raise RuntimeError(f"Nenhum banco de checkpoints encontrado em {checkpoint_path}")

        conn = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        thread_id = f"{project_id}-{task_id}"
        config = {"configurable": {"thread_id": thread_id}}

        graph = self._get_graph(checkpointer=checkpointer)
        snapshot = graph.get_state(config)

        if not snapshot or not snapshot.values:
            raise RuntimeError(f"Nenhum checkpoint encontrado para o thread '{thread_id}'.")

        last_values = snapshot.values
        resuming_node = snapshot.next[0] if snapshot.next else last_values.get("next_agent", "cpo")

        print(f"--- CHECKPOINT RECOVERY: Retomando pipeline (thread: {thread_id}) a partir do nó '{resuming_node}' ---")

        graph.update_state(config, {"error": None})

        self._broadcast_ws("pipeline_resumed", task_id, {
            "thread_id": thread_id,
            "resuming_from_node": resuming_node,
        })

        try:
            for event in graph.stream(None, config):
                for node_name, output in event.items():
                    if isinstance(output, dict):
                        self._broadcast_ws("node_execution", task_id, {
                            "node": node_name,
                            "next_agent": output.get("next_agent"),
                        })

            state_snapshot = graph.get_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            final_status = "completed" if not result.get("error") else "failed"
            final_event = "pipeline_finished" if final_status == "completed" else "pipeline_failed"
            self._broadcast_ws(final_event, task_id, {
                "status": final_status,
                "error": result.get("error"),
            })

            return result

        except Exception as e:
            self._broadcast_ws("pipeline_error", task_id, {"error": str(e)})
            return {**last_values, "error": str(e), "status": "failed"}
