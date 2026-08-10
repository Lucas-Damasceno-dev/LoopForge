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
import termios
import time
import tty
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from lf.api.events import event_bus
from lf.config.schema import TaskSchema
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.ontology.state_machine.definition import TaskState
from lf.ontology.state_machine.labels import get_git_label
from lf.pipeline.graph import build_graph
from lf.runner.git.checkpoint import GitCheckpointManager
from lf.runner.git.pr import create_github_pr

logger = logging.getLogger(__name__)


def _default_budget_usd() -> float:
    """M-08: fonte única do budget — ``ade.yaml budget.max_usd`` (default 10.0).

    Resolve em call-time (não import-time) para respeitar os.chdir()/
    monkeypatch.chdir() dos testes e da CLI. Falha silenciosamente para o
    default 10.0 se o arquivo estiver ausente ou inválido (mesmo espírito do
    load_ade_config().hitl.timeout_seconds usado no __init__).
    """
    try:
        from lf.config.loader import load_budget_usd

        return load_budget_usd()
    except Exception:
        return 10.0


def _task_dir_suffix(task: TaskSchema, project_id: str) -> str:
    """Sufixo de diretório único por task, sanitizado para um nome de pasta seguro.

    P1-4: o workdir era compartilhado entre todas as tasks de um projeto
    (`/tmp/loopforge/{project_id}`), permitindo contaminação cross-run (ex.:
    pom.xml/target/ de um run Java sobrevivendo num run Python). O id da task
    costuma embutir o prefixo do projeto (ex.: 'proj-x/task-run-abc'); esse
    prefixo é removido para evitar duplicação, e qualquer '/' remanescente vira
    '-'. Id vazio → '' (fallback: diretório do projeto, sem sufixo extra).
    """
    task_id = str(getattr(task, "id", "") or "")
    if not task_id:
        return ""
    if project_id and task_id.startswith(f"{project_id}/"):
        task_id = task_id[len(project_id) + 1 :]
    return task_id.replace("/", "-")


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
        hitl_timeout_seconds: int | None = None,
        hitl_on_timeout: str | None = None,
    ):
        self.mock_llm = mock_llm
        self.interactive = interactive
        self.circuit_breaker = circuit_breaker
        self.review_mode = review_mode
        self.notify = notify
        self.webhook_url = webhook_url
        if hitl_timeout_seconds is None:
            from lf.config.loader import load_ade_config

            hitl_timeout_seconds = load_ade_config().hitl.timeout_seconds
        self.hitl_timeout_seconds = hitl_timeout_seconds
        # C4 (M-11): comportamento ao esgotar o timeout do gate (fonte única
        # ade.yaml hitl.on_timeout; continue/abort/pause).
        if hitl_on_timeout is None:
            from lf.config.loader import load_ade_config

            hitl_on_timeout = load_ade_config().hitl.on_timeout
        self.hitl_on_timeout = hitl_on_timeout
        # C4 (M-11): gates HITL já anunciados (dedup do evento hitl_gate_reached
        # por run+nó — re-entrada no MESMO gate não re-publica).
        self._announced_hitl_gates: set[tuple[str, str]] = set()
        self._last_graph = None
        if self.circuit_breaker is None:
            self.circuit_breaker = CircuitBreaker(max_total_cost=_default_budget_usd())

    def _resolve_circuit_breaker(self):
        if self.circuit_breaker is not None:
            return self.circuit_breaker
        return CircuitBreaker(max_total_cost=_default_budget_usd())

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
            # P1-4: isolamento cross-run — diretório único por task para impedir
            # que artefatos de um run (pom.xml, target/, test_reports/) contaminem o
            # workdir do próximo. Fallback: diretório do projeto quando o id é vazio.
            "output_dir": "/".join(
                part for part in ("/tmp/loopforge", project_id, _task_dir_suffix(task, project_id)) if part
            ),
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
            "llm_model_name": os.getenv("OPENROUTER_MODEL")
            or os.getenv("OPENCODE_MODEL")
            or ("inclusionai/ling-3.0-flash:free" if os.getenv("OPENROUTER_API_KEY") else "gemini-2.0-flash"),
            "llm_temperature": 0.3,
            "routing_mode": getattr(task, "routing_mode", "full"),
            "task_type": getattr(task, "task_type", "feature"),
            "complexity_level": getattr(task, "complexity_level", "standard"),
            "is_interactive": self.interactive,
            "expected_schema": None,
            "persona_id": getattr(task, "agent_id", None),
            "circuit_breaker": self._resolve_circuit_breaker().snapshot(),
        }

        if shared_state:
            for k, v in shared_state.items():
                if v and k not in ("error", "next_agent"):
                    state[k] = v
        state["circuit_breaker"] = self._resolve_circuit_breaker().snapshot()

        return state

    def _broadcast_ws(
        self,
        event_type: str,
        task_id: str,
        payload: dict,
        thread_id: str | None = None,
        run_id: str | None = None,
    ):
        """Emite evento via EventBus (A3/M-05): persiste no journal + broadcast envelope v1.

        O EventBus é o emissor único — não há mais chamada direta ao
        ws_manager aqui. O evento é persistido na tabela ``events`` e
        broadcastado como envelope v1 ``{seq, event, run_id, timestamp,
        payload}`` (ADR-0002). O ``task_id`` é mantido DENTRO do payload (a
        SPA consome até o B1).

        O ``run_id`` do journal é derivado do ``thread_id`` via
        ``_resolve_telemetry_run_id``: no fluxo API o thread é ``run-{uuid}``
        e o journal fica chaveado pelo uuid (a mesma chave do GET
        /api/v1/runs/{id}/events e de human_decisions). Call sites sem
        thread_id (ex.: CLI legada) caem no ``task_id`` tal qual. A2/M-07:
        quando ``run_id`` é passado explicitamente (dispatcher canônico), ele
        vence a derivação — para runs CLI o journal fica chaveado pelo MESMO
        id da linha em pipeline_runs (backfill GET /runs/{id}/events funciona
        para runs CLI).

        Retorna a Task agendada quando há loop ativo (o caller async pode
        aguardá-la via ``_publish_event_async`` para garantir persistência em
        ordem de seq); retorna None em contexto síncrono (o publish roda
        bloqueante via ``asyncio.run``).
        """
        if run_id is None:
            run_id = self._resolve_telemetry_run_id(thread_id or task_id)
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(event_bus.publish(run_id, event_type, {**payload, "task_id": task_id}))
        except RuntimeError:
            try:
                asyncio.run(event_bus.publish(run_id, event_type, {**payload, "task_id": task_id}))
            except Exception as exc:
                logger.warning("Falha ao publicar evento via EventBus: %s", exc)
            return None

    async def _publish_event_async(
        self,
        event_type: str,
        task_id: str,
        payload: dict,
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Aguarda a publicação do evento (seq ordenado e sem fire-and-forget).

        Usado pelos caminhos async (_dispatch_async/_resume_async): o await na
        Task agendada por _broadcast_ws evita o race de seq do create_task
        solto (COUNT+1 concorrente gerava seq duplicados/fora de ordem).
        """
        scheduled = self._broadcast_ws(event_type, task_id, payload, thread_id=thread_id, run_id=run_id)
        if isinstance(scheduled, (asyncio.Task, asyncio.Future)):
            try:
                await scheduled
            except Exception as exc:
                logger.warning("Falha ao publicar evento via EventBus: %s", exc)

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

    def _get_single_key_with_timeout(self, prompt_text: str, timeout: float = 0.5) -> str:
        """Lê uma única tecla sem exigir Enter (modo cbreak), com timeout.

        Usa termios/tty para desligar ICANON e ECHO no TTY (tty.setcbreak
        mantém ISIG ligado, então ^C continua levantando KeyboardInterrupt —
        comportamento de aborto preservado). Retorna a tecla pressionada
        (1 char) ou '' no timeout, sem imprimir mensagem de timeout (evita spam).
        Em ambiente não-TTY (ex: pytest), faz fallback para
        _get_input_with_timeout para preservar o comportamento dos testes.
        """
        if prompt_text:
            print(prompt_text, end="", flush=True)
        if not sys.stdin.isatty():
            return self._get_input_with_timeout("", timeout)

        fd = sys.stdin.fileno()
        old_settings = None
        try:
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                raw = os.read(fd, 3).decode(errors="ignore")
                return raw[:1]
            return ""
        except Exception:
            try:
                return input()[:1]
            except Exception:
                # Fallback consistente com o timeout Unix (aborta em vez de aprovar)
                return "x"
        finally:
            if old_settings is not None:
                with contextlib.suppress(Exception):
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _ensure_human_decisions_table(self, db_path: Path) -> None:
        """Garante que a tabela human_decisions exista no SQLite de telemetria.

        Evita o erro 'no such table: human_decisions' quando o SELECT de
        decisão remota roda antes de qualquer INSERT (a tabela era criada
        apenas de forma lazy em _record_decision).
        """
        try:
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
                    timestamp TEXT NOT NULL,
                    state_patch TEXT
                )
            """)
            # C3 (M-12): migração aditiva da coluna state_patch — tabelas criadas
            # pelo ORM (models.HumanDecisionModel) não declaram a coluna.
            cols = {row[1] for row in cursor.execute("PRAGMA table_info(human_decisions)")}
            if "state_patch" not in cols:
                cursor.execute("ALTER TABLE human_decisions ADD COLUMN state_patch TEXT")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"--- AVISO: Falha ao garantir tabela human_decisions: {e} ---")

    def _poll_remote_decision_once(self, run_id: str) -> dict | None:
        """Consulta única à tabela human_decisions por decisão remota.

        Retorna {"action", "category", "message", "state_patch"} se houver
        decisão pendente para o run_id, ou None caso contrário. Não bloqueia.
        ``state_patch`` (C3/M-12) é decodificado de JSON quando presente.
        """
        if not run_id or run_id in ("default-run", "test", "test-run", "test-thread"):
            return None

        db_path = Path(".loopforge/telemetry.sqlite").resolve()
        if not db_path.exists():
            return None

        self._ensure_human_decisions_table(db_path)

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT action, feedback_category, feedback_message, state_patch "
                "FROM human_decisions WHERE run_id = ? ORDER BY timestamp DESC LIMIT 1",
                (run_id,),
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                result: dict = {"action": row[0], "category": row[1], "message": row[2]}
                if row[3]:
                    with contextlib.suppress(json.JSONDecodeError):
                        result["state_patch"] = json.loads(row[3])
                return result
        except Exception as exc:
            logger.warning("Falha ao verificar decisão remota: %s", exc)
        return None

    @staticmethod
    def _resolve_telemetry_run_id(thread_id: str) -> str:
        """Deriva o run_id usado em human_decisions a partir do thread_id.

        Per ADR-0003 (M-22) a API grava human_decisions.run_id = uuid, mas o
        thread da run é `run-{uuid}` (formato novo) ou `run-{uuid}-task-{uuid[:8]}`
        (formato legado/backfill). Extrai o uuid para o polling consultar a
        tabela pela mesma chave que a API usa. Threads fora do padrão 'run-'
        (CLI/legadas) são usadas tal qual.
        """
        if not thread_id.startswith("run-"):
            return thread_id
        run_id = thread_id[len("run-") :]
        if "-task-" in run_id:
            run_id = run_id.split("-task-", 1)[0]
        return run_id

    def _record_decision(
        self,
        run_id: str,
        gate_node: str,
        action: str,
        category: str | None = None,
        message: str | None = None,
        state_patch: dict | None = None,
    ):
        """Salva histórico de decisões humanas no SQLite.

        ``state_patch`` (C3/M-12) é serializado em JSON na coluna aditiva
        ``state_patch`` (garantida por _ensure_human_decisions_table).
        """
        try:
            db_path = Path(".loopforge/telemetry.sqlite").resolve()
            self._ensure_human_decisions_table(db_path)
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            decision_id = str(uuid.uuid4())
            now_iso = datetime.now(UTC).isoformat()
            patch_json = json.dumps(state_patch, ensure_ascii=False) if state_patch else None
            cursor.execute(
                "INSERT INTO human_decisions "
                "(id, run_id, gate_node, action, feedback_category, feedback_message, user, timestamp, state_patch) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (decision_id, run_id, gate_node, action, category, message, "human_operator", now_iso, patch_json),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"--- AVISO: Falha ao gravar decisão humana: {e} ---")

    def _pipeline_run_id(self, thread_id: str) -> str:
        """Id da linha em pipeline_runs (M-07/A2).

        Thread ``run-{uuid}`` (API) → o MESMO uuid que a API usa como id da
        run (o ON CONFLICT(id) atualiza a MESMA linha, sem duplicar). Thread
        CLI (``project-task-1``) → novo ``uuid4`` (não há run pré-criada); o
        thread real fica salvo na coluna ``thread_id``.
        """
        if thread_id.startswith("run-"):
            return self._resolve_telemetry_run_id(thread_id)
        return str(uuid.uuid4())

    def _upsert_pipeline_run(
        self,
        run_id: str,
        status: str,
        idea: str | None = None,
        stack: str | None = None,
        current_node: str | None = None,
        duration_seconds: float | None = None,
        thread_id: str | None = None,
    ) -> None:
        """Upsert idempotente em pipeline_runs (M-07/A2) — writer canônico.

        Runs CLI (`lf run --mock`) nunca passaram pelo ``create_all`` da API,
        então a tabela pode não existir: garante com o MESMO schema de
        models.PipelineRun (incluindo thread_id/parent_run_id) no MESMO db_path
        do ``_record_decision`` (``.loopforge/telemetry.sqlite``, resolvido em
        call-time). ``INSERT ... ON CONFLICT(id) DO UPDATE`` preserva
        ``created_at`` e não sobrescreve ``idea``/``stack`` já gravados pela
        API quando não informados (cláusula CASE).

        Telemetria: NUNCA derruba a pipeline (try/except + logger.warning).
        """
        try:
            db_path = Path(".loopforge/telemetry.sqlite").resolve()
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(db_path), timeout=10.0)
            conn.execute("PRAGMA busy_timeout=5000")
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pipeline_runs (
                        id VARCHAR(36) PRIMARY KEY,
                        idea TEXT NOT NULL,
                        stack VARCHAR(50) DEFAULT 'python',
                        status VARCHAR(20) DEFAULT 'pending',
                        current_node VARCHAR(50),
                        logs TEXT,
                        duration_seconds FLOAT DEFAULT 0.0,
                        thread_id VARCHAR(50),
                        parent_run_id VARCHAR(36),
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Formato de timestamp do SQLAlchemy no SQLite (space-separated,
                # sem tz) para o ORM da API ler sem fricção (teste (c)).
                now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
                conn.execute(
                    """
                    INSERT INTO pipeline_runs
                        (id, idea, stack, status, current_node, duration_seconds,
                         thread_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        current_node = excluded.current_node,
                        duration_seconds = excluded.duration_seconds,
                        thread_id = excluded.thread_id,
                        updated_at = excluded.updated_at,
                        idea = CASE WHEN excluded.idea IS NOT NULL
                                    THEN excluded.idea ELSE pipeline_runs.idea END,
                        stack = CASE WHEN excluded.stack IS NOT NULL
                                     THEN excluded.stack ELSE pipeline_runs.stack END
                    """,
                    (
                        run_id,
                        idea or "",
                        stack or "python",
                        status,
                        current_node,
                        # A tabela pode ter sido criada pelo create_all da API
                        # (models.PipelineRun: Mapped[float] => NOT NULL, sem
                        # DEFAULT DB-side) — NULL quebraria o upsert "running".
                        0.0 if duration_seconds is None else duration_seconds,
                        thread_id,
                        now,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Falha ao gravar pipeline_runs (run %s): %s", run_id, exc)

    def _apply_state_patch_to_checkpoint(self, app, config: dict, patch: dict) -> None:
        """Aplica o state_patch ao estado do checkpoint (C3/M-12).

        No caminho HITL síncrono o grafo é compilado com ``SqliteSaver``
        (``aupdate_state`` lança NotImplementedError com saver síncrono), então
        usa ``update_state`` direto — o mesmo padrão dos demais actions do gate
        (retry/adjust_prompt). Para grafo compilado com ``AsyncSqliteSaver``
        (padrão do resume async), delega ``aupdate_state`` a um loop dedicado
        via ``asyncio.run`` (equivalente ao ``asyncio.to_thread`` do padrão
        async).

        NOTA (documentado): canais fora do ``GraphState`` TypedDict são
        descartados pelo LangGraph — ``update_state`` só persiste chaves que são
        canais declarados (idea, stack, routing_mode, requirements, code,
        next_agent, etc.). Campos arbitrários não sobrevivem ao checkpoint.
        """
        if not patch:
            return
        saver_name = type(getattr(app, "checkpointer", None)).__name__
        if "Async" in saver_name:
            asyncio.run(app.aupdate_state(config, patch))
        else:
            app.update_state(config, patch)

    def _human_interrupt_handler(self, snapshot, config, app) -> bool:
        """Manipula interrupção humana (HITL) exibindo os artefatos do nó RECÉM-CONCLUÍDO e o gate do PRÓXIMO nó."""
        console = Console()
        next_node = snapshot.next[0] if snapshot.next else "unknown"
        node_name = next_node
        state = snapshot.values

        run_id = config.get("configurable", {}).get("thread_id", "default-run")
        # M-22 (ADR-0003): POST /decide grava human_decisions.run_id = uuid, mas
        # o thread da run é `run-{uuid}` (ou o legado `run-{uuid}-task-{uuid[:8]}`).
        # Extrai o uuid para consultar a tabela pelo mesmo run_id que a API usa —
        # antes o polling usava o thread_id e nunca casava com a decisão remota.
        telemetry_run_id = self._resolve_telemetry_run_id(run_id)

        # C4 (M-11): evento hitl_gate_reached na PRIMEIRA entrada do gate —
        # dedup por (run, nó) evita re-publicação em re-entradas no mesmo gate.
        if (telemetry_run_id, next_node) not in self._announced_hitl_gates:
            self._announced_hitl_gates.add((telemetry_run_id, next_node))
            self._broadcast_ws(
                "hitl_gate_reached",
                run_id,
                {
                    "gate_node": next_node,
                    "thread_id": run_id,
                    "run_id": telemetry_run_id,
                    "timeout_seconds": self.hitl_timeout_seconds,
                    "on_timeout": self.hitl_on_timeout,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )

        if self.notify:
            title = f"⏸️ Pipeline Pausado — Gate antes de {next_node.upper()}"
            msg_text = f"LoopForge aguardando aprovação humana antes de executar o nó {next_node}."
            _send_notification(title, msg_text, webhook_url=self.webhook_url)

        console.print(
            "\n[bold yellow]═══════════════════════════════════════════════════════════════════[/bold yellow]"
        )
        console.print(
            f"[bold yellow]⏸️  HUMAN-IN-THE-LOOP GATE — Próximo Nó: [bold white]{next_node.upper()}[/bold white][/bold yellow]"
        )
        console.print(
            "[bold yellow]═══════════════════════════════════════════════════════════════════[/bold yellow]\n"
        )

        # 1. Se estamos pausados antes de QA, o nó que recém-executou foi o DEVELOPER -> mostra o código gerado
        if next_node == "qa":
            code = state.get("code", "")
            console.print("[bold cyan]📝 Código Gerado pelo Developer (preview):[/bold cyan]")
            if any(err_kw in code for err_kw in ["Model not found", "UnknownError", "Error:", "xdotool:"]):
                console.print()
                console.print("[bold red]┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓[/bold red]")
                console.print("[bold red]┃ ⚠️  ERRO: A saída do Developer contém ERRO do LLM/ferramenta[/bold red]")
                console.print("[bold red]┃    Não é código válido. Revise antes de aprovar.           [/bold red]")
                console.print(
                    "[bold red]┃    Sugestão: digite [yellow]r[/yellow] para retentar ou [yellow]a[/yellow] para ajustar o prompt.[/bold red]"
                )
                console.print("[bold red]┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛[/bold red]")
                console.print()

            if code:
                import re

                clean_code = re.sub(r"\x1b\[[0-9;]*m", "", str(code)[:600])
                try:
                    syntax = Syntax(
                        clean_code + ("..." if len(code) > 600 else ""), "python", theme="monokai", line_numbers=True
                    )
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
                table.add_row(
                    str(v.get("id", "-")), sev_fmt, str(v.get("rule_id", "-")), str(v.get("description", "-"))
                )
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

        timeout_mode = {"continue": "CONTINUAR", "abort": "ABORTAR", "pause": "AGUARDAR DECISÃO TARDIA"}.get(
            self.hitl_on_timeout, "CONTINUAR"
        )
        console.print(f"\n[dim]Tempo limite: {self.hitl_timeout_seconds}s (ao esgotar: {timeout_mode})[/dim]")

        # Lê tecla única (sem Enter) com poll remoto curto intercalado para
        # não congelar o gate: (a) chama _get_single_key_with_timeout a cada
        # 0.5s; (b) se retornar tecla válida (c/r/a/x), processa; teclas
        # inválidas (\r, \n, '') são ignoradas e a espera continua; (c) entre
        # leituras faz poll remoto curto; (d) sai no deadline global
        # (hitl_timeout_seconds) ou quando houver decisão (local ou remota).
        #
        # C4 (M-11) on_timeout no esgotamento do deadline:
        #   continue = transição graciosa (legado, human_decision_expired);
        #   abort    = run falha controladamente (pipeline_failed, sem LLM);
        #   pause    = NÃO consome LLM, mantém o gate aberto re-aguardando a
        #              decisão tardia. gate_started (timestamp do início do
        #              gate) + flag timeout_elapsed distinguem 'expirado mas
        #              aguardando' de 'nunca expirou'.
        choice: str | None = None
        remote_decision: dict | None = None
        gate_started = time.monotonic()
        deadline = gate_started + self.hitl_timeout_seconds
        timeout_elapsed = False
        pause_announced = False
        poll_interval = 0.5
        valid_choices = ("c", "r", "a", "x")
        prompt_text = "➜ Escolha [c/r/a/x] (default: c): "
        while True:
            if time.monotonic() >= deadline:
                if self.hitl_on_timeout == "pause":
                    # Expirou MAS o gate permanece aberto (deadline vira
                    # infinito — não expira de novo). O timestamp do início
                    # do gate (gate_started) é a referência que distingue a
                    # decisão tardia ('expirado mas aguardando') da que veio
                    # dentro do prazo ('nunca expirou').
                    if not pause_announced:
                        pause_announced = True
                        console.print(
                            "\n[yellow]⏰ Tempo limite esgotado (on_timeout=pause). "
                            "Gate permanece aberto aguardando decisão tardia...[/yellow]"
                        )
                    deadline = float("inf")
                else:
                    timeout_elapsed = True
                    break
            raw_choice = self._get_single_key_with_timeout(prompt_text, poll_interval)
            prompt_text = ""
            if raw_choice in valid_choices:
                choice = raw_choice
                break
            remote_decision = self._poll_remote_decision_once(telemetry_run_id)
            if remote_decision:
                break

        if choice is None:
            if remote_decision:
                choice_map = {
                    "approve": "c",
                    "retry": "r",
                    "adjust_prompt": "a",
                    "adjust_state": "as",
                    "abort": "x",
                }
                choice = choice_map.get(remote_decision["action"], "c")
                console.print(
                    f"[bold green]➜ Decisão Remota via API Detectada: {remote_decision['action'].upper()}[/bold green]"
                )
            elif timeout_elapsed and self.hitl_on_timeout == "abort":
                # C4 (M-11) on_timeout=abort: run falha CONTROLADAMENTE sem
                # consumir LLM (nenhum nó é re-agendado). O estado final é
                # marcado como failed via update_state para o dispatcher
                # persistir status failed em pipeline_runs.
                reason = "hitl_timeout_abort"
                console.print(
                    f"\n[red]⏰ Tempo limite esgotado e on_timeout=abort: abortando pipeline ({reason}).[/red]"
                )
                self._broadcast_ws(
                    "pipeline_failed",
                    run_id,
                    {
                        "motivo": reason,
                        "node": next_node,
                        "timeout_seconds": self.hitl_timeout_seconds,
                        "run_status": "failed",
                    },
                )
                app.update_state(config, {"error": "HITL timeout sem decisão — abortado (on_timeout=abort)."})
                return False
            elif timeout_elapsed:
                # Timeout expirado sem decisão -> transição GRACIOSA (E10/F1-13):
                # NÃO aborta; continua a pipeline e marca a run como decision_expired.
                # NÃO grava em human_decisions (nenhuma decisão humana real foi
                # tomada) — decisão tardia via POST /api/runs/{run_id}/decide
                # continua aceita (poll ordena timestamp DESC, sem linha falsa).
                console.print(
                    "\n[yellow]⏰ Tempo limite de resposta esgotado. Continuando pipeline (default: c).[/yellow]"
                )
                run_status = "decision_expired"
                self._broadcast_ws(
                    "human_decision_expired",
                    run_id,
                    {
                        "node": next_node,
                        "timeout_seconds": self.hitl_timeout_seconds,
                        "run_status": run_status,
                    },
                )
                choice = "continue"

        action = "approve"
        cat = None
        msg = None

        if choice == "x":
            action = "abort"
            console.print("[red]Pipeline abortado pelo operador humano.[/red]")
            self._record_decision(telemetry_run_id, node_name, action, cat, msg)
            return False

        elif choice == "r":
            action = "retry"
            app.update_state(config, {"error": None})
            self._record_decision(telemetry_run_id, node_name, action, cat, msg)
            return True

        elif choice == "a":
            action = "adjust_prompt"
            console.print("\n[bold cyan]✏️  Feedback Estruturado (Request Changes):[/bold cyan]")
            console.print("  Categoria: [1] Bug  [2] Style  [3] Missing Feature  [4] General")
            cat_choice = self._get_input_with_timeout("➜ Categoria [1-4] (default: 4): ", timeout=60) or "4"
            cat_map = {"1": "bug", "2": "style", "3": "missing_feature", "4": "general"}
            cat = cat_map.get(cat_choice.strip(), "general")

            msg = (
                self._get_input_with_timeout("➜ Mensagem detalhada de feedback: ", timeout=120)
                or "Ajustar implementação."
            )

            app.update_state(
                config,
                {
                    "error": None,
                    "feedback_history": state.get("feedback_history", [])
                    + [
                        {
                            "from": "human",
                            "node": node_name,
                            "category": cat,
                            "message": msg,
                        }
                    ],
                },
            )
            self._record_decision(telemetry_run_id, node_name, action, cat, msg)
            return True

        elif choice == "as":
            # C3 (M-12) action=adjust_state (via POST /decide): aplica o
            # state_patch ao checkpoint e a run prossegue (mesmo efeito de
            # approve/continue). Campos fora do GraphState são descartados
            # pelo LangGraph (documentado em _apply_state_patch_to_checkpoint).
            action = "adjust_state"
            patch = (remote_decision or {}).get("state_patch") or {}
            if patch:
                self._apply_state_patch_to_checkpoint(app, config, patch)
                console.print(
                    f"[bold cyan]✏️  Estado ajustado via state_patch ({len(patch)} campo(s)). Continuando...[/bold cyan]"
                )
            else:
                console.print(
                    "[bold yellow]⚠️  action=adjust_state sem state_patch — continuando sem alterações.[/bold yellow]"
                )
            self._record_decision(telemetry_run_id, node_name, action, cat, msg, state_patch=patch or None)
            return True

        elif choice == "continue":
            # Timeout expirado (E10/F1-13): pipeline continua, mas NENHUMA
            # decisão humana é registrada — o audit trail fica intacto.
            console.print("[bold yellow]⏭️  Continuando após timeout — nenhuma decisão humana registrada.[/bold yellow]")
            return True

        else:
            action = "approve"
            console.print("[bold green]✅ Passo Aprovado. Continuando...[/bold green]")
            self._record_decision(telemetry_run_id, node_name, action, cat, msg)
            return True

    def _review_mode_approval_gate(self, final_state: dict) -> bool:
        """Modo Revisão: Exibe o plano/artefatos completos e solicita aprovação final antes de escrever em disco."""
        console = Console()
        console.print(
            "\n[bold magenta]═══════════════════════════════════════════════════════════════════[/bold magenta]"
        )
        console.print("[bold magenta]🔍 MODO REVISÃO INTERATIVA — APROVAÇÃO DE MUDANÇAS[/bold magenta]")
        console.print(
            "[bold magenta]═══════════════════════════════════════════════════════════════════[/bold magenta]\n"
        )

        console.print(f"[bold]Ideia / Objetivo:[/bold] {final_state.get('idea')}")
        console.print(f"[bold]Épico CPO:[/bold] {final_state.get('epic', {}).get('title', 'N/A')}")
        console.print(f"[bold]User Stories PM:[/bold] {len(final_state.get('user_stories', []))} estória(s)")
        console.print(f"[bold]Tech Spec Tech Lead:[/bold] {final_state.get('tech_spec', '')[:150]}...")
        console.print(
            f"[bold]DevOps Score:[/bold] {final_state.get('devops_review', {}).get('deployability_score', 100.0)}/100"
        )

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

    def _trajectories_db(self) -> Path:
        """Caminho do banco de trajetórias resolvido no momento da chamada.

        Resolve em call-time (não em import-time) para respeitar os.chdir()
        usado pelos testes e pela CLI em diretórios de trabalho arbitrários.
        """
        return Path(".loopforge/trajectories.db").resolve()

    def _safe_output(self, output: dict) -> dict:
        """Extrai campos seguros de um output de nó para broadcast via WebSocket."""
        return {
            "next_agent": output.get("next_agent"),
            "attempt_count": output.get("attempt_count", 0),
        }

    def list_checkpoints(self) -> list[str]:
        """Lista todos os thread_ids com trajetórias gravadas em .loopforge/trajectories.db."""
        if not self._trajectories_db().exists():
            return []
        import asyncio

        return asyncio.run(self._list_checkpoints_async())

    async def _list_checkpoints_async(self) -> list[str]:
        """Lê os thread_ids únicos do banco de trajetórias via AsyncSqliteSaver.alist."""
        from lf.pipeline.checkpointer import create_async_checkpointer

        checkpointer = create_async_checkpointer(self._trajectories_db())
        try:
            await checkpointer.setup()
            thread_ids: set[str] = set()
            async for item in checkpointer.alist(None):
                cfg = item.config or {}
                thread_id = (cfg.get("configurable") or {}).get("thread_id")
                if thread_id:
                    thread_ids.add(thread_id)
            return sorted(thread_ids)
        except Exception as e:
            print(f"--- AVISO: Falha ao listar checkpoints: {e} ---")
            return []
        finally:
            await checkpointer.conn.close()

    def dispatch(self, task: TaskSchema, project_id: str = "project", shared_state: dict | None = None) -> dict:
        """Executa a pipeline e persiste a trajetória em .loopforge/trajectories.db.

        Caminho padrão (não-interativo): roda o grafo via ``astream`` com
        AsyncSqliteSaver dentro de ``asyncio.run``. Caminho HITL (interactive):
        mantém o fluxo síncrono com ``_human_interrupt_handler`` via
        create_sync_checkpointer (regressão: testes HITL existentes passam sem
        refatoração do gate humano nesta migração).
        """
        initial_state = self._build_initial_state(task, project_id, shared_state=shared_state)
        # ADR-0003 (M-02): run e thread são 1:1 — a thread da run é `run-{run_id}`.
        # Quando project_id já é 'run-{uuid}' (chamada da API), usa-o direto,
        # removendo o sufixo legado '-task-{uuid[:8]}' do task.id.
        thread_id = project_id if project_id.startswith("run-") else f"{project_id}-{task.id}"

        if self.interactive:
            return self._dispatch_sync(initial_state, thread_id, task, project_id)

        import asyncio

        return asyncio.run(self._dispatch_async(initial_state, thread_id, task, project_id))

    async def _dispatch_async(self, initial_state: dict, thread_id: str, task: TaskSchema, project_id: str) -> dict:
        """Dispatcher assíncrono: astream + AsyncSqliteSaver em trajectories.db."""
        from lf.pipeline.checkpointer import create_async_checkpointer

        checkpointer = create_async_checkpointer(self._trajectories_db())
        task_id = task.id
        # A2/M-07: id da linha em pipeline_runs (1 por dispatch — CLI gera
        # uuid novo; API reusa o uuid da run) + duração da execução.
        pipeline_run_id = self._pipeline_run_id(thread_id)
        start_time = time.monotonic()

        try:
            await checkpointer.setup()
            graph = self._get_graph(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": thread_id}}

            self._upsert_pipeline_run(
                pipeline_run_id,
                "running",
                idea=initial_state.get("idea"),
                stack=initial_state.get("stack"),
                current_node=initial_state.get("next_agent"),
                thread_id=thread_id,
            )
            await self._publish_event_async(
                "pipeline_started",
                task_id,
                {"idea": initial_state.get("idea"), "node": initial_state.get("next_agent")},
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

            async for event in graph.astream(initial_state, config):
                for node_name, output in event.items():
                    if isinstance(output, dict):
                        await self._publish_event_async(
                            "node_execution",
                            task_id,
                            {
                                "node": node_name,
                                "status": "completed",
                                **self._safe_output(output),
                            },
                            thread_id=thread_id,
                            run_id=pipeline_run_id,
                        )

            state_snapshot = await graph.aget_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            if self.review_mode:
                approved = self._review_mode_approval_gate(result)
                if not approved:
                    result["error"] = "Review mode rejected by user"

            final_status = "completed" if not result.get("error") else "failed"
            final_event = "pipeline_finished" if final_status == "completed" else "pipeline_failed"
            self._upsert_pipeline_run(
                pipeline_run_id,
                final_status,
                idea=initial_state.get("idea"),
                stack=initial_state.get("stack"),
                current_node=result.get("next_agent", "FINISH"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            await self._publish_event_async(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

            if self.notify:
                status_label = "Concluído com Sucesso!" if not result.get("error") else "Falhou."
                _send_notification(
                    "🚀 Pipeline Finalizado", f"Task {task_id}: {status_label}", webhook_url=self.webhook_url
                )

            self._create_pr_with_labels(task, result, project_id)
            return result

        except Exception as e:
            self._upsert_pipeline_run(
                pipeline_run_id,
                "failed",
                idea=initial_state.get("idea"),
                stack=initial_state.get("stack"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            await self._publish_event_async(
                "pipeline_error",
                task_id,
                {"error": str(e)},
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )
            return {**initial_state, "error": str(e), "status": "failed"}

        finally:
            await checkpointer.conn.close()

    def _dispatch_sync(self, initial_state: dict, thread_id: str, task: TaskSchema, project_id: str) -> dict:
        """Dispatcher síncrono (caminho HITL): mantém _human_interrupt_handler e graph.stream.

        Usa create_sync_checkpointer no mesmo trajectories.db para compat com a
        Task 2; a refatoração do gate humano para o caminho async fica para uma
        task futura (regressão dos testes HITL tem prioridade nesta migração).
        """
        from lf.pipeline.checkpointer import create_sync_checkpointer

        checkpointer = create_sync_checkpointer(self._trajectories_db())
        graph = self._get_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        task_id = task.id
        # A2/M-07: mesmo id de linha por dispatch (1 por execução).
        pipeline_run_id = self._pipeline_run_id(thread_id)
        start_time = time.monotonic()

        self._upsert_pipeline_run(
            pipeline_run_id,
            "running",
            idea=initial_state.get("idea"),
            stack=initial_state.get("stack"),
            current_node=initial_state.get("next_agent"),
            thread_id=thread_id,
        )
        self._broadcast_ws(
            "pipeline_started",
            task_id,
            {"idea": task.title, "node": initial_state.get("next_agent")},
            thread_id=thread_id,
            run_id=pipeline_run_id,
        )

        try:
            for event in graph.stream(initial_state, config):
                for node_name, output in event.items():
                    if isinstance(output, dict):
                        self._broadcast_ws(
                            "node_execution",
                            task_id,
                            {
                                "node": node_name,
                                "status": "completed",
                                **self._safe_output(output),
                            },
                            thread_id=thread_id,
                            run_id=pipeline_run_id,
                        )

            if self.interactive:
                snapshot = graph.get_state(config)
                while snapshot.next:
                    proceed = self._human_interrupt_handler(snapshot, config, graph)
                    if not proceed:
                        break
                    for event in graph.stream(None, config):
                        for node_name, output in event.items():
                            if isinstance(output, dict):
                                self._broadcast_ws(
                                    "node_execution",
                                    task_id,
                                    {
                                        "node": node_name,
                                        "status": "completed",
                                        **self._safe_output(output),
                                    },
                                    thread_id=thread_id,
                                    run_id=pipeline_run_id,
                                )
                    snapshot = graph.get_state(config)

            state_snapshot = graph.get_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            if self.review_mode:
                approved = self._review_mode_approval_gate(result)
                if not approved:
                    result["error"] = "Review mode rejected by user"

            final_status = "completed" if not result.get("error") else "failed"
            final_event = "pipeline_finished" if final_status == "completed" else "pipeline_failed"
            self._upsert_pipeline_run(
                pipeline_run_id,
                final_status,
                idea=initial_state.get("idea"),
                stack=initial_state.get("stack"),
                current_node=result.get("next_agent", "FINISH"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            self._broadcast_ws(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

            if self.notify:
                status_label = "Concluído com Sucesso!" if not result.get("error") else "Falhou."
                _send_notification(
                    "🚀 Pipeline Finalizado", f"Task {task_id}: {status_label}", webhook_url=self.webhook_url
                )

            self._create_pr_with_labels(task, result, project_id)
            return result

        except Exception as e:
            self._upsert_pipeline_run(
                pipeline_run_id,
                "failed",
                idea=initial_state.get("idea"),
                stack=initial_state.get("stack"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            self._broadcast_ws(
                "pipeline_error", task_id, {"error": str(e)}, thread_id=thread_id, run_id=pipeline_run_id
            )
            return {**initial_state, "error": str(e), "status": "failed"}

        finally:
            checkpointer.conn.close()

    def resume(self, project_id: str = "project", task_id: str = "task-1", thread_id: str | None = None) -> dict:
        """Retoma a execução de uma pipeline a partir do último nó bem-sucedido via trajectories.db.

        ADR-0003 (M-01): a API passa o thread_id PERSISTIDO em pipeline_runs
        (formato `run-{run_id}`); project_id/task_id seguem como fallback para
        chamadas CLI/legadas (mesma regra do dispatch: project_id 'run-{uuid}'
        já é a thread).
        """
        if not self._trajectories_db().exists():
            raise RuntimeError(f"Nenhum banco de trajetórias encontrado em {self._trajectories_db()}")
        import asyncio

        return asyncio.run(self._resume_async(project_id, task_id, thread_id))

    async def _resume_async(self, project_id: str, task_id: str, thread_id: str | None = None) -> dict:
        """Resume assíncrono: aget_state/aupdate_state/astream sobre AsyncSqliteSaver."""
        from lf.pipeline.checkpointer import create_async_checkpointer

        checkpointer = create_async_checkpointer(self._trajectories_db())
        await checkpointer.setup()
        graph = self._get_graph(checkpointer=checkpointer)
        # Mesma regra do dispatch (M-02): 'run-{uuid}' é a thread canônica da
        # run; caso contrário deriva '{project_id}-{task_id}' (formato CLI).
        if thread_id is None:
            thread_id = project_id if project_id.startswith("run-") else f"{project_id}-{task_id}"
        config = {"configurable": {"thread_id": thread_id}}
        # A2/M-07: id da linha em pipeline_runs (API reusa o uuid da run).
        pipeline_run_id = self._pipeline_run_id(thread_id)
        start_time = time.monotonic()

        last_values: dict = {}
        try:
            snapshot = await graph.aget_state(config)

            if not snapshot or not snapshot.values:
                raise RuntimeError(f"Nenhum checkpoint encontrado para o thread '{thread_id}'.")

            last_values = snapshot.values
            resuming_node = snapshot.next[0] if snapshot.next else last_values.get("next_agent", "cpo")

            print(
                f"--- CHECKPOINT RECOVERY: Retomando pipeline (thread: {thread_id}) a partir do nó '{resuming_node}' ---"
            )

            await graph.aupdate_state(config, {"error": None})

            self._upsert_pipeline_run(
                pipeline_run_id,
                "running",
                idea=last_values.get("idea"),
                stack=last_values.get("stack"),
                current_node=resuming_node,
                thread_id=thread_id,
            )
            await self._publish_event_async(
                "pipeline_resumed",
                task_id,
                {
                    "thread_id": thread_id,
                    "resuming_from_node": resuming_node,
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

            async for event in graph.astream(None, config):
                for node_name, output in event.items():
                    if isinstance(output, dict):
                        await self._publish_event_async(
                            "node_execution",
                            task_id,
                            {
                                "node": node_name,
                                "status": "completed",
                                **self._safe_output(output),
                            },
                            thread_id=thread_id,
                            run_id=pipeline_run_id,
                        )

            state_snapshot = await graph.aget_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            final_status = "completed" if not result.get("error") else "failed"
            final_event = "pipeline_finished" if final_status == "completed" else "pipeline_failed"
            self._upsert_pipeline_run(
                pipeline_run_id,
                final_status,
                idea=last_values.get("idea"),
                stack=last_values.get("stack"),
                current_node=result.get("next_agent", "FINISH"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            await self._publish_event_async(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

            return result

        except Exception as e:
            self._upsert_pipeline_run(
                pipeline_run_id,
                "failed",
                idea=last_values.get("idea"),
                stack=last_values.get("stack"),
                duration_seconds=round(time.monotonic() - start_time, 2),
                thread_id=thread_id,
            )
            await self._publish_event_async(
                "pipeline_error", task_id, {"error": str(e)}, thread_id=thread_id, run_id=pipeline_run_id
            )
            return {**last_values, "error": str(e), "status": "failed"}

        finally:
            await checkpointer.conn.close()
