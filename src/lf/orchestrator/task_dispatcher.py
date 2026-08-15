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
from typing import Any

from rich.console import Console
from rich.syntax import Syntax

from lf.api.events import event_bus
from lf.config.schema import TaskSchema
from lf.config.workdir import get_workdir_base, is_within
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
        subprocess_timeout_seconds: int | None = None,
        sandbox_enabled: bool | None = None,
        # S3 (editor de pipelines): pipeline custom (PipelineBase) + templates
        # da biblioteca (dict id -> AgentBase). Ausentes = fluxo atual
        # (build_graph default). O snapshot do pipeline é IMUTÁVEL por run —
        # quem chama o dispatcher passa o snapshot reconstruído como pydantic.
        pipeline: Any | None = None,
        agent_templates: dict | None = None,
    ):
        self.mock_llm = mock_llm
        self.interactive = interactive
        self.circuit_breaker = circuit_breaker
        # M3: último estado de circuit_breaker PUBLICADO (dedup por transição).
        self._published_cb_state: str | None = None
        self.review_mode = review_mode
        self.notify = notify
        self.webhook_url = webhook_url
        self.pipeline = pipeline
        self.agent_templates = agent_templates or {}
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
        # P2-5: timeout de subprocesso configurável (ade.yaml
        # runner.subprocess_timeout_seconds; 0 = sem timeout). Antes era
        # hardcoded (120s) nas entradas interativas do gate — insuficiente
        # para modelos de reasoning. Fonte única: mesmo padrão do hitl acima.
        if subprocess_timeout_seconds is None:
            from lf.config.loader import load_ade_config

            subprocess_timeout_seconds = load_ade_config().runner.subprocess_timeout_seconds
        self.subprocess_timeout_seconds = subprocess_timeout_seconds
        # Item 4.1 roadmap: sandbox em git worktree (.slim/worktrees/) — geração
        # e testes rodam isolados; merge na main apenas após aprovação QA+AppSec.
        # Fonte única: ade.yaml runner.sandbox_enabled (mesmo padrão do hitl).
        from lf.config.loader import load_ade_config

        ade_config = load_ade_config()
        self.sandbox_enabled = sandbox_enabled if sandbox_enabled is not None else ade_config.runner.sandbox_enabled
        if self.sandbox_enabled and ade_config.runner.max_concurrent_runs > 1:
            logger.warning(
                "Sandbox habilitada com runner.max_concurrent_runs > 1: runs paralelas no MESMO repo "
                "competem por branches/worktrees — mitigação recomendada: flock por worktree "
                "(serialização) ou max_concurrent_runs=1."
            )
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

    def _ade_pipeline(self) -> Any:
        """Config pipeline do ade.yaml (v7 5.1) resolvida em call-time.

        Mesmo padrão do hitl/subprocesso no __init__: fonte única
        ``ade.yaml pipeline.*``; arquivo ausente → AdePipeline() com defaults.
        """
        from lf.config.loader import load_ade_config

        return load_ade_config().pipeline

    def _get_graph(self, checkpointer=None):
        """Retorna grafo compilado (cache por sessão).

        S3 (editor de pipelines): se a run foi criada com pipeline_id, monta o
        grafo a partir do SNAPSHOT via build_pipeline_graph (agent_templates da
        biblioteca resolvidos na execução; agente deletado → ValueError claro).
        Senão, fluxo atual (build_graph default, HITL gates habilitados).
        """
        if self.pipeline is not None:
            from lf.pipeline.pipeline_graph import build_pipeline_graph

            return build_pipeline_graph(
                self.pipeline,
                self.agent_templates,
                checkpointer=checkpointer,
            )
        return build_graph(
            checkpointer=checkpointer,
            human_gate_enabled=self.interactive,
        )

    def _build_initial_state(
        self,
        task: TaskSchema,
        project_id: str,
        shared_state: dict | None = None,
        run_key: str | None = None,
    ) -> dict:
        target_agent = getattr(task, "agent_id", None) or getattr(task, "persona", None) or "cpo"
        if target_agent not in ("cpo", "pm", "tech_lead", "developer", "qa"):
            target_agent = "cpo"

        ontology = "examples/the-foundry"
        if not Path(ontology).exists():
            repo_ontology = Path(__file__).resolve().parents[3] / "examples" / "the-foundry"
            if repo_ontology.exists():
                ontology = str(repo_ontology)

        # P1-4/AUD-2026-08: isolamento cross-run — diretório único por EXECUÇÃO.
        # O componente da run (run_key) é um uuid novo por dispatch no fluxo CLI
        # (project_id constante "loopforge_project" + task.id fixo "task-1"
        # colidiam entre runs consecutivas); no fluxo API é o próprio project_id
        # "run-{uuid}" (o shared_state já aponta output_dir, este valor é
        # sobrescrito). O run_key fica persistido no estado → o resume restaura
        # o MESMO workdir via checkpoint, sem recomputar nada.
        component = run_key or project_id
        state = {
            "idea": task.title,
            "output_dir": "/".join(
                part
                for part in (
                    get_workdir_base(),
                    component,
                    _task_dir_suffix(task, project_id),
                )
                if part
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
            # Modelo LLM da run: override explícito (task.model, ex. campo
            # `model` do POST /api/v1/runs) preenche o canal llm_model_name —
            # os nós o leem via resolve_model() (vence env/config). Ausente →
            # None: comportamento atual (resolve_default_model nos nós).
            "llm_model_name": getattr(task, "model", None),
            # Fix 1: run_id/task_id preenchidos no dispatch (a thread canônica
            # `run-{uuid}` só é derivada depois do _build_initial_state); o nó
            # developer usa o run_id p/ dimensionar custos em llm_costs. O
            # canal do TypedDict (state.py) pode não declarar run_id — nesse
            # caso o LangGraph descarta a chave e os nós caem no fallback via
            # config (resolve_run_id em lf/runner/opencode/llm.py).
            "run_id": None,
            "task_id": getattr(task, "id", None),
            "routing_mode": getattr(task, "routing_mode", "full"),
            "task_type": getattr(task, "task_type", "feature"),
            "complexity_level": getattr(task, "complexity_level", "standard"),
            # Milestone v7 5.1: entrega incremental por user story. A flag vem do
            # task OU do ade.yaml (pipeline.incremental_slices); os slices em si
            # são derivados das user_stories no nó PM (build_slices).
            "incremental_slices": bool(getattr(task, "incremental_slices", False))
            or bool(self._ade_pipeline().incremental_slices),
            "slices": [],
            "slice_index": 0,
            "slice_status": "",
            "slice_test_report": {},
            "test_scope": "full",
            "slice_max_retries": int(self._ade_pipeline().slice_max_retries),
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

    def _sandbox_task_slug(self, task: TaskSchema) -> str:
        """Slug do task.id sanitizado para branch/pasta de worktree (+ sufixo uuid).

        O sufixo uuid garante unicidade entre runs consecutivas do CLI (task.id
        é fixo — "task-1") que, sem ele, colidiriam na MESMA worktree/branch.
        """
        import re

        raw = str(getattr(task, "id", "") or "").lower()
        slug = re.sub(r"[^a-z0-9-]+", "-", raw).strip("-")
        if not slug:
            slug = "task"
        return f"{slug[:40]}-{uuid.uuid4().hex[:8]}"

    def _setup_sandbox(self, initial_state: dict, task: TaskSchema) -> dict | None:
        """Cria git worktree isolada (.slim/worktrees/) para a run, se habilitado.

        Item 4.1: geração/testes rodam em worktree separada; o merge na main só
        acontece após aprovação QA+AppSec (_finalize_sandbox). Degrada para None
        (execução SEM isolamento) com log quando: sandbox desabilitada; repo
        candidato não é git válido; repo é o próprio LoopForge (dogfooding); ou
        a criação da worktree falha — nunca quebra o dispatch.
        """
        if not self.sandbox_enabled:
            return None
        from lf.runner.git.sandbox import GitSandbox

        # Repo candidato: project_dir se for caminho real != "."; senão cwd.
        project_dir = str(initial_state.get("project_dir") or ".")
        if project_dir != "." and Path(project_dir).is_dir():
            repo = Path(project_dir).resolve()
        else:
            repo = Path(os.getcwd()).resolve()

        if not GitSandbox.is_git_repo(repo):
            logger.debug("Sandbox: '%s' não é repo git válido — execução sem isolamento.", repo)
            return None

        # Dogfooding: nunca isolar o próprio repo LoopForge.
        loopforge_root = Path(__file__).resolve().parents[3]
        if repo == loopforge_root or (repo / ".loopforge.json").exists():
            logger.warning("Sandbox: repo LoopForge detectado (%s) — sandbox ignorada.", repo)
            return None

        slug = self._sandbox_task_slug(task)
        sandbox = GitSandbox(repo)
        try:
            worktree = sandbox.create_worktree(slug)
        except Exception as exc:
            logger.warning("Falha ao criar worktree sandbox em %s: %s", repo, exc)
            return None
        if worktree is None:
            logger.warning("Sandbox: create_worktree(%s) falhou em %s — degradação silenciosa.", slug, repo)
            return None

        return {
            "enabled": True,
            "repo": str(repo),
            "worktree_path": str(worktree),
            "task_id": slug,
            "branch": f"lf-worktree-{slug}",
        }

    def _finalize_sandbox(self, sandbox: dict | None, result: dict, approved: bool) -> None:
        """Finaliza a sandbox: merge na main SÓ se aprovado E sem erros/falhas/vulns.

        Aprovado: limpa artefatos regeneráveis (artifacts_only) → commit na
        worktree → merge na main → remove worktree+branch. Não aprovado:
        remove worktree+branch SEM merge (o código fica só na branch temporária,
        descartada). Nunca propaga exceção — degradação com warning.
        """
        if not sandbox or not sandbox.get("enabled"):
            return
        from lf.runner.git.sandbox import GitSandbox

        git = GitSandbox(sandbox["repo"])
        task_id = sandbox["task_id"]
        try:
            tests_failed = result.get("test_report", {}).get("summary", {}).get("tests_failed")
            vulns = result.get("security_report", {}).get("vulnerabilities_found")
            ok = approved and not result.get("error") and not tests_failed and not vulns
            if ok:
                from lf.pipeline.nodes.developer import _cleanup_stale_project_dirs

                _cleanup_stale_project_dirs(
                    [sandbox["worktree_path"]],
                    stack=str(result.get("stack", "")),
                    artifacts_only=True,
                )
                if git.commit_worktree(task_id, f"feat: código gerado por {task_id}"):
                    if git.merge_worktree(task_id):
                        git.cleanup_worktree(task_id)
                    else:
                        logger.warning("Sandbox: merge da worktree %s falhou — worktree removida sem merge.", task_id)
                        git.cleanup_worktree(task_id)
                else:
                    logger.warning("Sandbox: nada a commitar na worktree %s — worktree removida.", task_id)
                    git.cleanup_worktree(task_id)
            else:
                logger.warning(
                    "Sandbox: run NÃO aprovada para merge (approved=%s, error=%r, tests_failed=%r, vulns=%r) "
                    "— worktree %s removida sem merge.",
                    approved,
                    bool(result.get("error")),
                    tests_failed,
                    vulns,
                    task_id,
                )
                git.cleanup_worktree(task_id)
        except Exception as exc:
            logger.warning("Falha ao finalizar sandbox (%s): %s", task_id, exc)
            with contextlib.suppress(Exception):
                git.cleanup_worktree(task_id)

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

    def _cb_from_snapshot(self, state_snapshot, fallback: dict | None = None) -> dict | None:
        """Snapshot do CircuitBreaker a publicar (M3).

        Prefere o payload do interrupt de budget (hard-stop M-10): o interrupt
        ABORTA o retorno do nó developer, então o canal do estado não carrega o
        CB atualizado (LangGraph passa CÓPIA do estado ao nó) — o payload leva o
        snapshot no instante da transição closed→open.
        """
        for it in getattr(state_snapshot, "interrupts", None) or ():
            iv = getattr(it, "value", None)
            if isinstance(iv, dict) and iv.get("paused_budget"):
                payload = iv.get("circuit_breaker")
                if isinstance(payload, dict):
                    return payload
                break
        return fallback if isinstance(fallback, dict) else None

    def _publish_cb_transition(self, cb_snapshot, task_id, thread_id, pipeline_run_id):
        """Publica ``circuit_breaker_changed`` SÓ em TRANSIÇÃO de estado (M3).

        Dedup por estado atual: o snapshot (dict de 10 campos, mesmo shape do
        publish no finally da API) só é emitido quando ``state`` muda desde a
        última publicação. Retorna a Task de _broadcast_ws (None se nada
        mudou): em contexto async dá para ``await`` (ordenação); em contexto
        sync é fire-and-forget (mesmo padrão do node_execution).
        """
        if not isinstance(cb_snapshot, dict) or not isinstance(cb_snapshot.get("state"), str):
            return None
        state = cb_snapshot["state"]
        if state == self._published_cb_state:
            return None
        self._published_cb_state = state
        scheduled = self._broadcast_ws(
            "circuit_breaker_changed",
            task_id,
            cb_snapshot,
            thread_id=thread_id,
            run_id=pipeline_run_id,
        )
        # Só devolve Task/Future REAL (para await em contexto async): em contexto
        # sync _broadcast_ws já executou/disparou; se um teste stubou o método
        # com MagicMock, não há o que aguardar (await em MagicMock → TypeError).
        if isinstance(scheduled, (asyncio.Task, asyncio.Future)):
            return scheduled
        return None

    def _get_input_with_timeout(self, prompt_text: str, timeout: float = 300) -> str:
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
                # Sem TTY/stdin fechado (ex: execução headless): NÃO há operador
                # humano — retorna '' para o gate seguir no polling REMOTO em vez
                # de abortar (o fallback antigo retornava 'x' e matava a run).
                return ""

    def _get_single_key_with_timeout(self, prompt_text: str, timeout: float = 0.5) -> str:
        """Lê uma única tecla sem exigir Enter (modo cbreak), com timeout.

        Usa termios/tty para desligar ICANON e ECHO no TTY (tty.setcbreak
        mantém ISIG ligado, então ^C continua levantando KeyboardInterrupt —
        comportamento de aborto preservado). Retorna a tecla pressionada
        (1 char) ou '' no timeout, sem imprimir mensagem de timeout (evita spam).
        Em ambiente não-TTY (ex: pytest, API headless), faz fallback para
        _get_input_with_timeout — o '' resultante é ignorado pelo gate, que
        segue no polling REMOTO (B3).
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
                    state_patch TEXT,
                    consumed BOOLEAN DEFAULT 0
                )
            """)
            # C3 (M-12): migração aditiva da coluna state_patch — tabelas criadas
            # pelo ORM (models.HumanDecisionModel) não declaram a coluna. B2:
            # consumed (filtro do polling por run_id+gate_node) na mesma guarda.
            cols = {row[1] for row in cursor.execute("PRAGMA table_info(human_decisions)")}
            if "state_patch" not in cols:
                cursor.execute("ALTER TABLE human_decisions ADD COLUMN state_patch TEXT")
            if "consumed" not in cols:
                cursor.execute("ALTER TABLE human_decisions ADD COLUMN consumed BOOLEAN DEFAULT 0")
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"--- AVISO: Falha ao garantir tabela human_decisions: {e} ---")

    def _poll_remote_decision_once(self, run_id: str, gate_node: str | None = None) -> dict | None:
        """Consulta única à tabela human_decisions por decisão remota.

        Retorna {"id", "action", "category", "message", "state_patch"} se
        houver decisão PENDENTE (consumed=0) para o (run_id, gate_node), ou
        None caso contrário. Não bloqueia.
        ``state_patch`` (C3/M-12) é decodificado de JSON quando presente.
        B2: o filtro agora casa (run_id, gate_node) — antes era só run_id e uma
        decisão aprovada num gate re-aplicava no próximo (append-only).
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
            if gate_node:
                cursor.execute(
                    "SELECT id, action, feedback_category, feedback_message, state_patch "
                    "FROM human_decisions WHERE run_id = ? AND gate_node = ? AND consumed = 0 "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (run_id, gate_node),
                )
            else:
                cursor.execute(
                    "SELECT id, action, feedback_category, feedback_message, state_patch "
                    "FROM human_decisions WHERE run_id = ? AND consumed = 0 "
                    "ORDER BY timestamp DESC LIMIT 1",
                    (run_id,),
                )
            row = cursor.fetchone()
            conn.close()
            if row:
                result: dict = {"id": row[0], "action": row[1], "category": row[2], "message": row[3]}
                if row[4]:
                    with contextlib.suppress(json.JSONDecodeError):
                        result["state_patch"] = json.loads(row[4])
                return result
        except Exception as exc:
            logger.warning("Falha ao verificar decisão remota: %s", exc)
        return None

    def _mark_decision_consumed(self, decision_id: str | None) -> None:
        """Marca a decisão remota como CONSUMIDA (B2) — o polling é append-only
        e, sem a flag, a MESMA decisão re-aplicava em gates subsequentes."""
        if not decision_id:
            return
        try:
            db_path = Path(".loopforge/telemetry.sqlite").resolve()
            self._ensure_human_decisions_table(db_path)
            conn = sqlite3.connect(str(db_path))
            try:
                conn.execute("UPDATE human_decisions SET consumed = 1 WHERE id = ?", (decision_id,))
                conn.commit()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("Falha ao marcar decisão como consumida: %s", exc)

    def _existing_pipeline_run_flags(self, run_id: str) -> tuple[bool, str | None]:
        """Lê degraded/degraded_reason persistidos de pipeline_runs (B7).

        O resume preserva as flags da run pausada no upsert final — o estado do
        checkpoint pode não carregar degraded (a flag foi gravada só no DB).
        """
        try:
            db_path = Path(".loopforge/telemetry.sqlite").resolve()
            if not db_path.exists():
                return False, None
            conn = sqlite3.connect(str(db_path), timeout=10.0)
            try:
                row = conn.execute(
                    "SELECT degraded, degraded_reason FROM pipeline_runs WHERE id = ?", (run_id,)
                ).fetchone()
            finally:
                conn.close()
            if row:
                return bool(row[0]), (row[1] if isinstance(row[1], str) else None)
        except Exception as exc:
            logger.warning("Falha ao ler flags degradadas da run %s: %s", run_id, exc)
        return False, None

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
                "INSERT INTO human_decisions (id, run_id, gate_node, action, feedback_category, "
                "feedback_message, user, timestamp, state_patch, consumed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
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
        degraded: bool = False,
        degraded_reason: str | None = None,
    ) -> None:
        """Upsert idempotente em pipeline_runs (M-07/A2) — writer canônico.

        Runs CLI (`lf run --mock`) nunca passaram pelo ``create_all`` da API,
        então a tabela pode não existir: garante com o MESMO schema de
        models.PipelineRun (incluindo thread_id/parent_run_id/degraded) no MESMO
        db_path do ``_record_decision`` (``.loopforge/telemetry.sqlite``,
        resolvido em call-time). ``INSERT ... ON CONFLICT(id) DO UPDATE``
        preserva ``created_at`` e não sobrescreve ``idea``/``stack`` já gravados
        pela API quando não informados (cláusula CASE).

        ``degraded`` (coluna NOT NULL sem default DB-side quando a tabela foi
        criada pelo create_all da API) SEMPRE recebe valor — 0/False por padrão,
        o status real nos upserts finais — senão o INSERT quebra com
        ``NOT NULL constraint failed`` e a run CLI nunca vira linha.

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
                        degraded BOOLEAN DEFAULT 0,
                        degraded_reason TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # DBs legados (criados antes das colunas degraded existirem) não
                # são alterados por CREATE TABLE IF NOT EXISTS — migra aditivamente
                # (mesmo padrão de app._ensure_pipeline_runs_degraded_columns).
                existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)").fetchall()}
                if "degraded" not in existing_cols:
                    conn.execute("ALTER TABLE pipeline_runs ADD COLUMN degraded BOOLEAN DEFAULT 0")
                if "degraded_reason" not in existing_cols:
                    conn.execute("ALTER TABLE pipeline_runs ADD COLUMN degraded_reason TEXT")
                # Formato de timestamp do SQLAlchemy no SQLite (space-separated,
                # sem tz) para o ORM da API ler sem fricção (teste (c)).
                now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
                conn.execute(
                    """
                    INSERT INTO pipeline_runs
                        (id, idea, stack, status, current_node, duration_seconds,
                         thread_id, degraded, degraded_reason, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        current_node = excluded.current_node,
                        duration_seconds = excluded.duration_seconds,
                        thread_id = excluded.thread_id,
                        degraded = excluded.degraded,
                        degraded_reason = CASE WHEN excluded.degraded_reason IS NOT NULL
                                               THEN excluded.degraded_reason
                                               ELSE pipeline_runs.degraded_reason END,
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
                        degraded,
                        degraded_reason,
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
        (métodos ``a*`` do saver síncrono lançam NotImplementedError), então
        usa ``update_state`` direto — o mesmo padrão dos demais actions do gate
        (retry/adjust_prompt). Para grafo compilado com ``AsyncSqliteSaver``
        (padrão do resume async), delega ``aupdate_state`` a um loop dedicado
        via thread + ``asyncio.run`` (equivalente ao ``asyncio.to_thread`` do
        padrão async) — seguro mesmo com loop já ativo na thread atual.

        A detecção é por ``isinstance`` (não por nome da classe): o
        ``SqliteSaver`` síncrono DEFINE ``aupdate_state`` como stub que levanta
        NotImplementedError, então ``hasattr``/nome de classe enganariam.

        NOTA (documentado): canais fora do ``GraphState`` TypedDict são
        descartados pelo LangGraph — ``update_state`` só persiste chaves que são
        canais declarados (idea, stack, routing_mode, requirements, code,
        next_agent, etc.). Campos arbitrários não sobrevivem ao checkpoint.
        """
        if not patch:
            return
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        checkpointer = getattr(app, "checkpointer", None)
        if isinstance(checkpointer, AsyncSqliteSaver):
            self._run_async_checkpoint_update(app.aupdate_state, config, patch)
            return
        app.update_state(config, patch)

    @staticmethod
    def _run_async_checkpoint_update(aupdate_state, config: dict, patch: dict) -> None:
        """Executa ``aupdate_state`` em loop dedicado, sem RuntimeError.

        ``asyncio.run`` com loop ativo na thread atual levanta RuntimeError. O
        ``AsyncSqliteSaver`` liga ``self.loop`` ao loop de criação (os shims
        sync delega-via-``run_coroutine_threadsafe``), mas ``aupdate_state`` em
        si não usa ``self.loop`` — rodar o coroutine numa thread própria com
        ``asyncio.run`` é o equivalente direto do ``asyncio.to_thread``.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(aupdate_state(config, patch))
            return

        import threading

        errors: list[BaseException] = []

        def _worker() -> None:
            try:
                asyncio.run(aupdate_state(config, patch))
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()
        worker.join()
        if errors:
            raise errors[0]

    def _render_hitl_diff_preview(self, state: dict) -> None:
        """Renderiza diff side-by-side (máx. 5 arquivos) entre output_dir e o workspace.

        Item 4.4 do roadmap: no gate HITL antes do QA, mostra lado a lado o que o
        Developer gerou (output_dir) contra o alvo (project_dir ou diretório atual).
        É PURE display: não altera fluxo de escolha, polling, timeouts ou eventos WS.

        Degrada SILENCIOSAMENTE para a linha "Nenhuma diferença" quando output_dir
        não existe, o alvo é inválido ou ocorre qualquer erro — nunca lança exceção
        que quebre o gate HITL.
        """
        console = Console()
        try:
            # Import local (evita carregar o grupo click no import top-level do
            # dispatcher). Sem risco de cycle: diff.py só importa click e workdir.
            from lf.cli.commands.diff import _render_side_by_side_files
        except Exception:
            _render_side_by_side_files = None  # type: ignore[assignment]

        console.print("\n[bold cyan]📊 Diff Side-by-Side (arquivos gerados vs workspace):[/bold cyan]")
        try:
            proposed_dir = Path(state.get("output_dir") or "").resolve()
            if not proposed_dir.is_dir():
                console.print("[green]Nenhuma diferença entre arquivos gerados e o workspace.[/green]")
                return

            # Alvo do diff: project_dir se existir e for caminho válido; senão o
            # diretório atual (mesmo comportamento do diff.py: target = ".").
            target_path = Path(state.get("project_dir") or ".").resolve()
            if not target_path.is_dir():
                target_path = Path(".").resolve()

            if proposed_dir == target_path:
                console.print("[green]Nenhuma diferença entre arquivos gerados e o workspace.[/green]")
                return

            diffs: list[tuple[str, str, str]] = []
            for p in proposed_dir.rglob("*"):
                if not p.is_file():
                    continue
                rel: str = str(p.relative_to(proposed_dir))
                target_file = target_path / rel
                proposed_text = p.read_text(errors="ignore")
                original_text = target_file.read_text(errors="ignore") if target_file.exists() else ""
                if proposed_text != original_text:
                    diffs.append((rel, original_text, proposed_text))

            if not diffs:
                console.print("[green]Nenhuma diferença entre arquivos gerados e o workspace.[/green]")
                return

            # Máx. 5 arquivos para não inundar o console; conteúdo truncado em
            # 3000 chars por arquivo (o preview de código usa o mesmo critério).
            for rel, original, proposed in diffs[:5]:
                if _render_side_by_side_files is not None:
                    _render_side_by_side_files(
                        rel,
                        original[:3000] + ("..." if len(original) > 3000 else ""),
                        proposed[:3000] + ("..." if len(proposed) > 3000 else ""),
                    )
                else:
                    console.print(f"[bold yellow]📄 {rel}:[/bold yellow]")

            extra = len(diffs) - 5
            if extra > 0:
                console.print(f"[dim]... e {extra} arquivo(s) adicionais com diferenças[/dim]")
        except Exception as exc:  # pragma: no cover - degradação defensiva
            logger.debug("Diff side-by-side no gate HITL indisponível: %s", exc)
            console.print("[green]Nenhuma diferença entre arquivos gerados e o workspace.[/green]")

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

            # Item 4.4 do roadmap: diff side-by-side (arquivos gerados vs workspace)
            # logo após o preview do código, antes da lista de ações. Só exibição.
            self._render_hitl_diff_preview(state)

        # 2. Se estamos pausados antes do DEVELOPER, mostra a especificação do TECH LEAD
        elif next_node == "developer":
            tech_spec = state.get("tech_spec", "")
            console.print("[bold cyan]📋 Especificação Técnica do Tech Lead (preview):[/bold cyan]")
            if tech_spec:
                console.print(f"[dim]{tech_spec[:500]}...[/dim]")
            else:
                console.print("[dim]Nenhuma especificação disponível.[/dim]")

        console.print("\n[bold]Ações Disponíveis:[/bold]")
        console.print("  [green]c[/green] — Continuar / Aprovar")
        console.print("  [yellow]r[/yellow] — Retentar nó anterior")
        console.print("  [blue]a[/blue] — Solicitar alterações / Ajustar Prompt (Request Changes)")
        console.print("  [magenta]d[/magenta] — Ver Diff side-by-side das alterações")
        console.print("  [red]x[/red] — Abortar pipeline")

        timeout_mode = {"continue": "CONTINUAR", "abort": "ABORTAR", "pause": "AGUARDAR DECISÃO TARDIA"}.get(
            self.hitl_on_timeout, "CONTINUAR"
        )
        console.print(f"\n[dim]Tempo limite: {self.hitl_timeout_seconds}s (ao esgotar: {timeout_mode})[/dim]")

        # Lê tecla única (sem Enter) com poll remoto curto intercalado para
        # não congelar o gate: (a) chama _get_single_key_with_timeout a cada
        # 0.5s; (b) se retornar tecla válida (c/r/a/d/x), processa; teclas
        # inválidas (\r, \n, '') são ignoradas e a espera continua; (c) entre
        # leituras faz poll remoto curto; (d) sai no deadline global
        # (hitl_timeout_seconds) ou quando houver decisão (local ou remota).
        choice: str | None = None
        remote_decision: dict | None = None
        gate_started = time.monotonic()
        deadline = gate_started + self.hitl_timeout_seconds
        timeout_elapsed = False
        pause_announced = False
        poll_interval = 0.5
        prompt_text = "➜ Escolha [c/r/a/d/x] (default: c): "
        while True:
            if time.monotonic() >= deadline:
                if self.hitl_on_timeout == "pause":
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
            if raw_choice == "d":
                self._render_hitl_diff_preview(state)
                prompt_text = "\n➜ Escolha [c/r/a/d/x] (default: c): "
                continue
            if raw_choice in ("c", "r", "a", "x"):
                choice = raw_choice
                break
            remote_decision = self._poll_remote_decision_once(telemetry_run_id, next_node)
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
                # B2: decisão aplicada → marcada como consumida (o polling é
                # append-only; sem a flag ela re-aplicaria no próximo gate).
                self._mark_decision_consumed(remote_decision.get("id"))
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
            # B3: decisão remota traz feedback_category/feedback_message — aplica
            # direto SEM stdin e propaga category/message para o novo prompt.
            remote_fb = remote_decision or {}
            if remote_fb.get("category") or remote_fb.get("message"):
                cat = remote_fb.get("category") or "general"
                msg = remote_fb.get("message") or "Ajustar implementação."
                console.print(f"[bold cyan]✏️  Feedback Remoto via API: [{cat}] {msg}[/bold cyan]")
            elif not sys.stdin.isatty():
                # Sem TTY e sem feedback remoto: default sem bloquear (B3) —
                # antes o re-prompt por stdin travava 60s+ em execução headless.
                cat, msg = "general", "Ajustar implementação."
            else:
                console.print("\n[bold cyan]✏️  Feedback Estruturado (Request Changes):[/bold cyan]")
                console.print("  Categoria: [1] Bug  [2] Style  [3] Missing Feature  [4] General")
                cat_choice = self._get_input_with_timeout("➜ Categoria [1-4] (default: 4): ", timeout=60) or "4"
                cat_map = {"1": "bug", "2": "style", "3": "missing_feature", "4": "general"}
                cat = cat_map.get(cat_choice.strip(), "general")

                msg = (
                    self._get_input_with_timeout(
                        "➜ Mensagem detalhada de feedback: ", timeout=self.subprocess_timeout_seconds
                    )
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
        choice = (
            self._get_input_with_timeout("➜ Aplicar alterações? [s/N]: ", timeout=self.subprocess_timeout_seconds)
            .strip()
            .lower()
        )

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

    def _cleanup_task_workdir(self, final_state: dict) -> None:
        """P1-4/AUD-2026-08: remove artefatos regeneráveis do workdir da task ao final da run.

        Só age DENTRO do workdir base configurado (``LF_WORKDIR_BASE``) — nunca
        em path arbitrário (``is_within`` antes de qualquer remoção). Preserva o
        código-fonte gerado (git/PR/diff dependem dele); remove apenas artefatos
        de build/cache/dependência (target/, test_reports/, .venv/,
        node_modules/, __pycache__/) e manifestos/fontes estrangeiros à stack.
        """
        output_dir = final_state.get("output_dir")
        if not output_dir:
            return
        try:
            base = Path(get_workdir_base()).resolve()
            if not is_within(base, output_dir):
                logger.warning(
                    "--- AVISO: workdir da task fora da base configurada (%s) — limpeza ignorada: %s ---",
                    base,
                    output_dir,
                )
                return
            from lf.pipeline.nodes.developer import _cleanup_stale_project_dirs

            _cleanup_stale_project_dirs(
                [output_dir],
                stack=str(final_state.get("stack", "")),
                artifacts_only=True,
            )
        except Exception as exc:
            logger.warning("Falha ao limpar workdir da task ao final da run: %s", exc)

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

        # P1-4/AUD-2026-08: no fluxo CLI o project_id é constante
        # ("loopforge_project") e o task.id fixo ("task-1") — runs consecutivas
        # colidiam no MESMO output_dir. Gera um run_key uuid único por dispatch
        # (mesmo padrão do session_id CLI / _pipeline_run_id) e reconstrói o
        # estado com o workdir isolado. Fluxo API ("run-{uuid}") usa o próprio
        # project_id como componente — sem mudança de comportamento.
        if not project_id.startswith("run-"):
            run_key = f"run-{uuid.uuid4().hex[:12]}"
            initial_state["output_dir"] = "/".join(
                part
                for part in (
                    get_workdir_base(),
                    run_key,
                    _task_dir_suffix(task, project_id),
                )
                if part
            )

        # Item 4.1 roadmap: sandbox em git worktree — substitui o workdir da run
        # pelo caminho da worktree isolada (gera/testa lá; merge na main apenas
        # após aprovação QA+AppSec no finalize). project_dir TAMBÉM aponta para a
        # worktree: os nós (developer, lessons, appsec/devops, harness) operam só
        # dentro do isolamento — sem efeitos colaterais untracked no repo do
        # usuário, que quebrariam o merge (untracked overwritten). Snapshot
        # persistido no estado.
        sandbox_snapshot = self._setup_sandbox(initial_state, task)
        if sandbox_snapshot:
            initial_state["output_dir"] = sandbox_snapshot["worktree_path"]
            initial_state["project_dir"] = sandbox_snapshot["worktree_path"]
            initial_state["sandbox"] = sandbox_snapshot

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
        # Fix 1: run_id/task_id no estado ANTES da primeira chamada de nó —
        # o run_id é o MESMO id da linha em pipeline_runs que o GET
        # /api/v1/runs/{id}/cost usa para somar llm_costs. Se o canal não for
        # declarado no GraphState (state.py), o LangGraph descarta a chave e
        # os nós derivam o run_id do thread via resolve_run_id(config).
        initial_state["run_id"] = pipeline_run_id
        initial_state["task_id"] = task_id
        start_time = time.monotonic()
        # Item 4.1: snapshot da sandbox (se ativa) + flag de finalização para o
        # finally degradar SEM merge se a run morrer no meio.
        sandbox = initial_state.get("sandbox") or None
        sandbox_done = False

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
                        # M3: transição do CircuitBreaker observada no estado do
                        # nó → publica circuit_breaker_changed em tempo real.
                        _cb_task = self._publish_cb_transition(
                            output.get("circuit_breaker"), task_id, thread_id, pipeline_run_id
                        )
                        if _cb_task is not None:
                            await _cb_task

            state_snapshot = await graph.aget_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            # M3: cobre o estado FINAL (dedup idempotente — se a última
            # transição já emitiu o mesmo estado, nada é publicado de novo).
            # Hard-stop M-10: prefere o snapshot do interrupt (o canal não
            # carrega o CB novo) e reescreve o canal para o finally da API
            # não publicar estado STALE (closed) por cima.
            _cb_authoritative = self._cb_from_snapshot(state_snapshot, result.get("circuit_breaker"))
            if _cb_authoritative is not None:
                result["circuit_breaker"] = _cb_authoritative
            _cb_task = self._publish_cb_transition(_cb_authoritative, task_id, thread_id, pipeline_run_id)
            if _cb_task is not None:
                await _cb_task

            # Item 4.1: aprovação vale para o merge da sandbox — review mode só
            # aprova se o usuário confirmar; caso contrário o merge é negado.
            approved = not self.review_mode or self._review_mode_approval_gate(result)
            if not approved:
                result["error"] = "Review mode rejected by user"

            degraded = bool(result.get("degraded"))
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
                degraded=degraded,
            )
            await self._publish_event_async(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                    "degraded": degraded,
                    "note": (
                        "Execução degradada: fallback/mock em uso (LLM indisponível ou modo mock)."
                        if degraded
                        else None
                    ),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )
            self._cleanup_task_workdir(result)

            if self.notify:
                if degraded:
                    status_label = "Concluído com Sucesso (degradado — fallback/mock)!"
                else:
                    status_label = "Concluído com Sucesso!" if not result.get("error") else "Falhou."
                _send_notification(
                    "🚀 Pipeline Finalizado", f"Task {task_id}: {status_label}", webhook_url=self.webhook_url
                )

            if sandbox:
                # Item 4.1: merge na main SÓ com aprovação QA+AppSec. Caminho
                # async não tem HITL (interactive=False) — sem prompt.
                if self.interactive:
                    resp = self._get_input_with_timeout(
                        "[yellow]Mergear worktree na main? [s/N][/yellow]: ",
                        timeout=self.subprocess_timeout_seconds,
                    )
                    if resp.strip().lower() not in ("s", "sim", "y", "yes"):
                        approved = False
                self._finalize_sandbox(sandbox, result, approved)
                sandbox_done = True
            else:
                self._create_pr_with_labels(task, result, project_id)
            return result

        except Exception as e:
            # Item 1: traceback completo no log — a causa raiz da falha não
            # deve depender só do evento pipeline_error (sem stack).
            logger.exception("Falha na execução da pipeline (thread=%s, run=%s)", thread_id, pipeline_run_id)
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
            if sandbox and not sandbox_done:
                self._finalize_sandbox(sandbox, {**initial_state, "error": str(e), "status": "failed"}, approved=False)
                sandbox_done = True
            return {**initial_state, "error": str(e), "status": "failed"}

        finally:
            await checkpointer.conn.close()
            if sandbox and not sandbox_done:
                # Run morreu no meio (sem passar pelo except acima): degrada SEM
                # merge — a worktree é removida e o código descartado.
                self._finalize_sandbox(
                    sandbox,
                    {"error": "run interrompida — sandbox não finalizada"},
                    approved=False,
                )

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
        # Fix 1: run_id/task_id no estado antes da primeira chamada de nó
        # (mesma lógica do _dispatch_async — ver comentário lá).
        initial_state["run_id"] = pipeline_run_id
        initial_state["task_id"] = task_id
        start_time = time.monotonic()
        # Item 4.1: snapshot da sandbox (se ativa) + flag de finalização (mesmo
        # padrão do _dispatch_async — o finally degrada SEM merge se a run morrer).
        sandbox = initial_state.get("sandbox") or None
        sandbox_done = False

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
                        # M3: transição do CircuitBreaker (sync: fire-and-forget,
                        # mesmo padrão do node_execution acima).
                        self._publish_cb_transition(output.get("circuit_breaker"), task_id, thread_id, pipeline_run_id)

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
                                self._publish_cb_transition(
                                    output.get("circuit_breaker"), task_id, thread_id, pipeline_run_id
                                )
                    snapshot = graph.get_state(config)

            state_snapshot = graph.get_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            # M3: estado final (dedup idempotente) — hard-stop M-10 prefere o
            # snapshot do interrupt (canal não carrega o CB novo) e reescreve o
            # canal para o finally da API não publicar estado STALE.
            _cb_authoritative = self._cb_from_snapshot(state_snapshot, result.get("circuit_breaker"))
            if _cb_authoritative is not None:
                result["circuit_breaker"] = _cb_authoritative
            self._publish_cb_transition(_cb_authoritative, task_id, thread_id, pipeline_run_id)

            # Item 4.1: aprovação vale para o merge da sandbox — review mode só
            # aprova se o usuário confirmar; caso contrário o merge é negado.
            approved = not self.review_mode or self._review_mode_approval_gate(result)
            if not approved:
                result["error"] = "Review mode rejected by user"

            degraded = bool(result.get("degraded"))
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
                degraded=degraded,
            )
            self._broadcast_ws(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                    "degraded": degraded,
                    "note": (
                        "Execução degradada: fallback/mock em uso (LLM indisponível ou modo mock)."
                        if degraded
                        else None
                    ),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )
            self._cleanup_task_workdir(result)

            if self.notify:
                if degraded:
                    status_label = "Concluído com Sucesso (degradado — fallback/mock)!"
                else:
                    status_label = "Concluído com Sucesso!" if not result.get("error") else "Falhou."
                _send_notification(
                    "🚀 Pipeline Finalizado", f"Task {task_id}: {status_label}", webhook_url=self.webhook_url
                )

            if sandbox:
                # Item 4.1: no caminho HITL o usuário decide o merge na main
                # (default N — só "s/sim/y/yes" aprova). QA+AppSec já passaram;
                # este prompt é a última palavra do humano.
                if self.interactive:
                    resp = self._get_input_with_timeout(
                        "[yellow]Mergear worktree na main? [s/N][/yellow]: ",
                        timeout=self.subprocess_timeout_seconds,
                    )
                    if resp.strip().lower() not in ("s", "sim", "y", "yes"):
                        approved = False
                self._finalize_sandbox(sandbox, result, approved)
                sandbox_done = True
            else:
                self._create_pr_with_labels(task, result, project_id)
            return result

        except Exception as e:
            # Item 1: gate/execução HITL — traceback no log (thread/run).
            logger.exception("Falha na execução HITL (thread=%s, run=%s)", thread_id, pipeline_run_id)
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
            if sandbox and not sandbox_done:
                self._finalize_sandbox(sandbox, {**initial_state, "error": str(e), "status": "failed"}, approved=False)
                sandbox_done = True
            return {**initial_state, "error": str(e), "status": "failed"}

        finally:
            checkpointer.conn.close()
            if sandbox and not sandbox_done:
                # Run morreu no meio (sem passar pelo except acima): degrada SEM
                # merge — a worktree é removida e o código descartado.
                self._finalize_sandbox(
                    sandbox,
                    {"error": "run interrompida — sandbox não finalizada"},
                    approved=False,
                )

    async def _resume_gate_async(
        self,
        graph,
        config: dict,
        next_node: str,
        task_id: str,
        thread_id: str,
        pipeline_run_id: str,
    ) -> str:
        """Re-entra no gate HITL durante o resume (B4), no MESMO mecanismo do
        fluxo normal: anuncia ``hitl_gate_reached``, aguarda decisão remota via
        poll (run_id+gate_node) e aplica a ação ao checkpoint via aupdate_state.

        Retorna 'continue' (ou a ação aplicada) ou 'abort'. No timeout, segue
        ``hitl_on_timeout`` (continue default; abort marca erro; pause aguarda
        decisão tardia indefinidamente).
        """
        run_id = config.get("configurable", {}).get("thread_id", "default-run")
        telemetry_run_id = self._resolve_telemetry_run_id(run_id)

        # C4 (M-11): hitl_gate_reached na primeira entrada do gate (dedup por run+nó).
        if (telemetry_run_id, next_node) not in self._announced_hitl_gates:
            self._announced_hitl_gates.add((telemetry_run_id, next_node))
            await self._publish_event_async(
                "hitl_gate_reached",
                task_id,
                {
                    "gate_node": next_node,
                    "thread_id": run_id,
                    "run_id": telemetry_run_id,
                    "timeout_seconds": self.hitl_timeout_seconds,
                    "on_timeout": self.hitl_on_timeout,
                    "ts": datetime.now(UTC).isoformat(),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )

        # on_timeout=pause: gate permanece aberto aguardando decisão tardia.
        deadline = float("inf") if self.hitl_on_timeout == "pause" else time.monotonic() + self.hitl_timeout_seconds
        remote: dict | None = None
        while time.monotonic() < deadline:
            remote = self._poll_remote_decision_once(telemetry_run_id, next_node)
            if remote:
                break
            await asyncio.sleep(0.5)

        if not remote:
            if self.hitl_on_timeout == "abort":
                console = Console()
                console.print("\n[red]⏰ Tempo limite esgotado no resume (on_timeout=abort): abortando pipeline.[/red]")
                await graph.aupdate_state(
                    config, {"error": "HITL timeout sem decisão no resume — abortado (on_timeout=abort)."}
                )
                return "abort"
            # continue (default): segue sem registrar decisão humana (audit trail intacto).
            return "continue"

        self._mark_decision_consumed(remote.get("id"))
        action = remote.get("action", "approve")

        if action == "abort":
            await graph.aupdate_state(config, {"error": "Pipeline abortada via decisão remota no resume."})
            return "abort"

        if action == "retry":
            await graph.aupdate_state(config, {"error": None})
            return "continue"

        if action == "adjust_prompt":
            cat = remote.get("category") or "general"
            msg = remote.get("message") or "Ajustar implementação."
            snap = await graph.aget_state(config)
            history = list((snap.values or {}).get("feedback_history", []) or [])
            await graph.aupdate_state(
                config,
                {
                    "error": None,
                    "feedback_history": history
                    + [{"from": "human", "node": next_node, "category": cat, "message": msg}],
                },
            )
            return "continue"

        if action == "adjust_state":
            patch = remote.get("state_patch") or {}
            if patch:
                await graph.aupdate_state(config, patch)
            return "continue"

        # approve/continue
        await graph.aupdate_state(config, {"error": None})
        return "continue"

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
            # Item 4.1: resume de run em sandbox — se a worktree foi removida
            # entre a pausa e o resume (ex.: limpeza manual), recria a partir do
            # snapshot e aponta o output_dir para a worktree nova ANTES do astream.
            sandbox_state = last_values.get("sandbox") or {}
            if sandbox_state.get("enabled"):
                from lf.runner.git.sandbox import GitSandbox

                worktree_path = Path(sandbox_state["worktree_path"])
                if not worktree_path.exists():
                    sb = GitSandbox(sandbox_state["repo"])
                    recreated = sb.create_worktree(sandbox_state["task_id"])
                    if recreated is not None:
                        new_sandbox = {**sandbox_state, "worktree_path": str(recreated)}
                        await graph.aupdate_state(
                            config,
                            {
                                "output_dir": str(recreated),
                                "project_dir": str(recreated),
                                "sandbox": new_sandbox,
                            },
                        )
                        last_values["output_dir"] = str(recreated)
                        last_values["project_dir"] = str(recreated)
                        last_values["sandbox"] = new_sandbox
                    else:
                        logger.warning(
                            "Resume: não foi possível recriar worktree sandbox %s — seguindo sem isolamento.",
                            sandbox_state.get("task_id"),
                        )
            resuming_node = snapshot.next[0] if snapshot.next else last_values.get("next_agent", "cpo")

            # B4: gate HITL pendente no resume — o checkpoint parado em
            # interrupt (next != []) precisa re-entrar no loop de decisão ANTES
            # de continuar o astream. Distingue de pausa por budget (M-10):
            # o hard-stop usa interrupt() com payload `paused_budget`; o gate
            # (interrupt_after) não carrega __interrupt__.
            budget_paused = bool(
                getattr(snapshot, "interrupts", None)
                and any(
                    isinstance(getattr(i, "value", None), dict) and i.value.get("paused_budget")
                    for i in snapshot.interrupts
                )
            )
            pending_gate: str | None = None
            if snapshot.next and not budget_paused and bool(last_values.get("is_interactive")):
                candidate = snapshot.next[0]
                # Mesmo conjunto de gates do build_graph (human_gate_enabled).
                if candidate in ("developer", "qa", "parallel_audit"):
                    pending_gate = candidate

            if pending_gate:
                gate_action = await self._resume_gate_async(
                    graph, config, pending_gate, task_id, thread_id, pipeline_run_id
                )
                if gate_action == "abort":
                    self._upsert_pipeline_run(
                        pipeline_run_id,
                        "failed",
                        idea=last_values.get("idea"),
                        stack=last_values.get("stack"),
                        current_node=pending_gate,
                        thread_id=thread_id,
                    )
                    await self._publish_event_async(
                        "pipeline_failed",
                        task_id,
                        {"status": "failed", "error": "Pipeline abortada no gate durante o resume."},
                        thread_id=thread_id,
                        run_id=pipeline_run_id,
                    )
                    return {**last_values, "error": "Pipeline abortada no gate durante o resume.", "status": "failed"}

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
                        # M3: transição do CircuitBreaker no resume (mesmo dedup).
                        _cb_task = self._publish_cb_transition(
                            output.get("circuit_breaker"), task_id, thread_id, pipeline_run_id
                        )
                        if _cb_task is not None:
                            await _cb_task

            state_snapshot = await graph.aget_state(config)
            result = dict(state_snapshot.values) if state_snapshot and state_snapshot.values else {}

            # M3: estado final do resume (dedup idempotente) — hard-stop M-10
            # prefere o snapshot do interrupt e reescreve o canal.
            _cb_authoritative = self._cb_from_snapshot(state_snapshot, result.get("circuit_breaker"))
            if _cb_authoritative is not None:
                result["circuit_breaker"] = _cb_authoritative
            _cb_task = self._publish_cb_transition(_cb_authoritative, task_id, thread_id, pipeline_run_id)
            if _cb_task is not None:
                await _cb_task

            # B7: preserva degraded/degraded_reason persistidos da run pausada —
            # o estado do checkpoint pode não carregar a flag (ela foi gravada
            # só no DB) e o upsert final sobrescreveria com False.
            persisted_degraded, persisted_reason = self._existing_pipeline_run_flags(pipeline_run_id)
            degraded = bool(result.get("degraded")) or persisted_degraded
            degraded_reason = result.get("degraded_reason")
            if not isinstance(degraded_reason, str):
                degraded_reason = persisted_reason
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
                degraded=degraded,
                degraded_reason=degraded_reason,
            )
            await self._publish_event_async(
                final_event,
                task_id,
                {
                    "status": final_status,
                    "error": result.get("error"),
                    "degraded": degraded,
                    "note": (
                        "Execução degradada: fallback/mock em uso (LLM indisponível ou modo mock)."
                        if degraded
                        else None
                    ),
                },
                thread_id=thread_id,
                run_id=pipeline_run_id,
            )
            self._cleanup_task_workdir(result)

            return result

        except Exception as e:
            # Item 1: falha no resume — traceback no log (thread/run).
            logger.exception("Falha no resume (thread=%s, run=%s)", thread_id, pipeline_run_id)
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
