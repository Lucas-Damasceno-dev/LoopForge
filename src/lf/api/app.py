"""Aplicação FastAPI principal do LoopForge.

Expõe endpoints REST, WebSockets autenticados para streaming e Web Dashboard UI.
"""

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import time
from collections import deque
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, cast

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.auth import Principal, get_current_principal, verify_authentication
from lf.api.config import get_api_settings
from lf.api.dashboard_html import get_dashboard_html
from lf.api.database import close_db, get_session, init_db
from lf.api.events import event_bus
from lf.api.models import AgentTemplate, HumanDecisionModel, PipelineRun, PipelineTemplate
from lf.api.pipeline_validator import SPECIAL_AGENT_IDS, validate_pipeline
from lf.api.pipelines import PipelineBase
from lf.api.rate_limit import RateLimitMiddleware
from lf.api.schemas import (
    AuthMeResponse,
    HealthResponse,
    HumanDecisionCreate,
    HumanDecisionResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunUpdate,
)
from lf.api.spa import mount_spa
from lf.api.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Heartbeat app-level do WebSocket (item 2): sem mensagens por este intervalo,
# o servidor envia {"type":"ping"} — o frontend responde {"type":"pong"}.
WS_HEARTBEAT_INTERVAL = 30.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia ciclo de vida da aplicação: init do DB + crash recovery (C9)."""
    settings = get_api_settings()
    await init_db(settings)
    # Migração aditiva de pipeline_runs (degraded/degraded_reason): DBs legados
    # não têm as colunas — ALTER TABLE idempotente (padrão C3/M-12).
    _ensure_pipeline_runs_degraded_columns(_telemetry_db_path())
    # C9: a fila E3 é in-memory — crash do processo derrubou execução e fila.
    # Runs `running`/`queued` no DB não têm task ativa nem slot: viram `failed`
    # com motivo claro (resume recupera do checkpoint). Runs `paused` são
    # PRESERVADAS (checkpoint persiste — intenção M-10).
    await _recover_interrupted_runs(app)
    yield
    await close_db()


async def _recover_interrupted_runs(app: FastAPI) -> None:
    """Marca como ``failed`` runs órfãs (running/queued) no startup (C9)."""
    from lf.api.database import session_factory
    from lf.api.models import PipelineRun

    if not session_factory:
        return
    async with session_factory() as session:
        result = await session.execute(select(PipelineRun).where(PipelineRun.status.in_(["running", "queued"])))
        orphaned = list(result.scalars().all())
        for run in orphaned:
            run.status = "failed"
            run.logs = "Servidor reiniciou; use resume para retomar a execução"
        if orphaned:
            await session.commit()
    for run in orphaned:
        with contextlib.suppress(Exception):
            await event_bus.publish(
                run.id,
                "run_updated",
                {"status": "failed", "reason": "servidor reiniciou; use resume"},
            )


class RunQueueState:
    """Estado da fila de execução E3 (M-21): N runs ativas + FIFO de runs `queued`.

    ``pending`` guarda os run_ids na ordem de chegada; ``active`` é o conjunto
    das runs em execução (até ``max_concurrent``); ``params`` guarda os
    parâmetros de execução (idea, stack, mock_llm, routing_mode, interactive) —
    o PipelineRun não persiste esses campos, então são retidos em memória até a
    promoção.
    """

    def __init__(self, max_concurrent: int = 1) -> None:
        self.max_concurrent = max_concurrent
        self.pending: deque[str] = deque()
        self.active: set[str] = set()
        self.lock = asyncio.Lock()
        self.params: dict[str, dict] = {}


def _mark_legacy(response: Response) -> None:
    """Marca a resposta como rota legada /api/runs* (M-18): Sunset + Deprecation."""
    response.headers["Sunset"] = "2026-12-31"
    response.headers["Deprecation"] = "true"


def _telemetry_db_path() -> Path:
    """Caminho do banco de telemetria resolvido em call-time (regra do database.py).

    LF_API_TEST -> .loopforge/test_api.sqlite; caso contrário o default da API
    (sqlite+aiosqlite:///.loopforge/telemetry.sqlite). O dispatcher polla
    telemetry.sqlite no mesmo padrão — os dois precisam enxergar a MESMA
    tabela human_decisions para o polling do gate casar com o POST /decide.
    """
    if os.getenv("LF_API_TEST"):
        return Path(".loopforge/test_api.sqlite").resolve()
    return Path(".loopforge/telemetry.sqlite").resolve()


def _ensure_human_decisions_state_patch_column(db_path: Path) -> None:
    """Garante as colunas aditivas ``state_patch``/``consumed`` em human_decisions.

    O modelo ORM ``HumanDecisionModel`` (models.py) pode não declarar as
    colunas em DBs legados — elas são adicionadas via SQL direto com o mesmo
    espírito da migração aditiva de pipeline_runs em database.py. ``consumed``
    (B2): o polling do gate filtra decisões não consumidas por (run_id,
    gate_node); sem a coluna o SELECT quebraria. Telemetria: nunca derruba o
    request (try/except + warning).
    """
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            cols = {row[1] for row in conn.execute("PRAGMA table_info(human_decisions)")}
            if "state_patch" not in cols:
                conn.execute("ALTER TABLE human_decisions ADD COLUMN state_patch TEXT")
            if "consumed" not in cols:
                conn.execute("ALTER TABLE human_decisions ADD COLUMN consumed BOOLEAN DEFAULT 0")
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Falha ao garantir colunas em human_decisions: %s", exc)


def _ensure_pipeline_runs_degraded_columns(db_path: Path) -> None:
    """Garante as colunas aditivas ``degraded``/``degraded_reason`` em pipeline_runs.

    DBs legados (criados antes do campo de degradação) não têm as colunas — o
    ORM ``PipelineRun`` as declara, mas o create_all não altera tabelas
    existentes. Adiciona via ALTER TABLE idempotente (detecção por PRAGMA
    table_info), no mesmo espírito de ``_ensure_human_decisions_state_patch_column``.
    Telemetria: nunca derruba o startup (try/except + warning).
    """
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)")}
            if "degraded" not in cols:
                conn.execute("ALTER TABLE pipeline_runs ADD COLUMN degraded BOOLEAN DEFAULT 0")
            if "degraded_reason" not in cols:
                conn.execute("ALTER TABLE pipeline_runs ADD COLUMN degraded_reason TEXT")
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Falha ao garantir colunas degraded em pipeline_runs: %s", exc)


def create_app(ui_enabled: bool | None = None) -> FastAPI:
    """Factory da aplicação FastAPI oficial do LoopForge.

    Se ui_enabled for None, lê a env LF_UI_ENABLED ("0" desliga o dashboard/SPA).
    """
    settings = get_api_settings()
    if ui_enabled is None:
        ui_enabled = os.environ.get("LF_UI_ENABLED", "1") != "0"
    app = FastAPI(
        title="LoopForge API",
        description="API REST, WebSockets e Dashboard Web para gerenciamento de pipelines do LoopForge v6",
        version="6.0.0",
        lifespan=lifespan,
    )

    # Estado da fila E3 (M-21) — N runs ativas + fila FIFO (por instância da app).
    # max_concurrent_runs vem de ade.yaml (AdeRunner.max_concurrent_runs, default 2);
    # runs além do limite nascem `queued` e promovem quando um slot liberar.
    from lf.config.loader import load_ade_config

    app.state.run_queue = RunQueueState(max_concurrent=load_ade_config().runner.max_concurrent_runs)
    # C8: registry run_id → asyncio.Task em execução (para POST /cancel).
    # A fila em memória morre no restart — o crash recovery (C9) cobre isso.
    app.state.run_tasks = {}  # dict[str, asyncio.Task]

    # ─── Middleware: CORS (M-04) ───────────────────────────────────
    # Origens de LF_CORS_ORIGINS (vírgula) ou default ["*"]. Wildcard não
    # combina com allow_credentials=True (inválido/ignorado em browsers).
    cors_origins = settings.cors_origins_list()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Middleware: Request Timing & Logging ────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response

    # ─── Middleware: Rate Limit (in-memory, por IP/X-API-Key) ────────
    # Janela deslizante por minuto (LF_API_RATE_LIMIT_PER_MIN; 0 = desabilitado).
    # O middleware é HTTP-only: WebSockets não passam por ele, e /health e
    # preflights OPTIONS (CORS) são ignorados.
    if settings.rate_limit_per_min > 0:
        app.add_middleware(RateLimitMiddleware, limit_per_min=settings.rate_limit_per_min)

    # ─── Dashboard Web UI ───────────────────────────────────────────
    if ui_enabled:

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
        async def render_dashboard():
            """Serves the modern Glassmorphic Web Dashboard UI."""
            return HTMLResponse(content=get_dashboard_html())

    # ─── Health ─────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Verifica se a API e o banco estão operacionais."""
        return HealthResponse()

    # ─── WebSockets para Streaming em Tempo Real com Auth ───────────
    @app.websocket("/ws/streaming")
    @app.websocket("/ws/runs/{run_id}")
    async def websocket_endpoint(
        websocket: WebSocket,
        run_id: str | None = None,
        token: str | None = Query(None),
    ):
        """Conexão WebSocket com validação de autenticação se ativada."""
        # Se autenticação for exigida, valida token no query parameter
        if settings.require_auth or settings.api_key:
            expected_key = settings.api_key or "secret"
            if not token or token != expected_key:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return

        # M-06: /ws/runs/{run_id} registra canal FILTRADO por run
        # (ws_manager.connect(run_id, ws)); /ws/streaming segue global
        # (run_id=None → connect(ws) legado).
        await ws_manager.connect(run_id, websocket)
        try:
            await ws_manager.send_personal_message(
                {
                    "event": "connected",
                    "status": "streaming_active",
                    "run_id": run_id or "global",
                },
                websocket,
            )
            while True:
                # Heartbeat app-level (item 2): sem mensagens por ~30s (socket
                # meio-aberto/rede parcial), o servidor envia {"type":"ping"} —
                # o frontend responde {"type":"pong"} (contrato combinado). A
                # escrita é única: este loop é o único writer do socket no
                # endpoint (pong de resposta + heartbeat).
                try:
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=WS_HEARTBEAT_INTERVAL)
                except TimeoutError:
                    await ws_manager.send_personal_message({"type": "ping"}, websocket)
                    continue
                if data.get("type") == "ping":
                    await ws_manager.send_personal_message({"type": "pong"}, websocket)
                # "pong" = ack do heartbeat do servidor — sem resposta (evita loop).
        except WebSocketDisconnect:
            ws_manager.disconnect(run_id, websocket)
        except Exception:
            ws_manager.disconnect(run_id, websocket)

    # ─── CRUD & Execução de Runs ──────────────────────────────────
    async def _create_run_impl(payload: RunCreate, session: AsyncSession) -> PipelineRun:
        """Cria a run como `queued` e a enfileira na fila E3 (M-21).

        S3 (editor de pipelines): se payload.pipeline_id, carrega o template,
        revalida (defensivo — o template salvo pode ter sido editado para um
        estado inválido) e grava um SNAPSHOT IMUTÁVEL do pipeline no run. A
        execução usa sempre o snapshot — o template pode mudar/deletar depois.
        """
        run = PipelineRun(
            idea=payload.idea,
            stack=payload.stack,
            status="queued",
        )

        pipeline_snapshot: dict | None = None
        if payload.snapshot is not None:
            # Override do usuário no create-run: valida como pipeline real.
            pipeline = PipelineBase.model_validate(payload.snapshot)
            agents_result = await session.execute(select(AgentTemplate.id))
            known_agents = {row[0] for row in agents_result.all()} | SPECIAL_AGENT_IDS
            errors = validate_pipeline(pipeline, known_agents)
            if errors:
                raise HTTPException(status_code=422, detail=f"snapshot invalid: {', '.join(errors)}")
            pipeline_snapshot = pipeline.model_dump()
            if payload.pipeline_id:
                run.pipeline_id = payload.pipeline_id
        elif payload.pipeline_id:
            template = await session.get(PipelineTemplate, payload.pipeline_id)
            if template is None:
                raise HTTPException(status_code=404, detail="Pipeline not found")

            pipeline = PipelineBase(
                name=template.name,
                description=template.description,
                nodes=template.nodes,
                edges=template.edges,
            )
            agents_result = await session.execute(select(AgentTemplate.id))
            known_agents = {row[0] for row in agents_result.all()} | SPECIAL_AGENT_IDS
            errors = validate_pipeline(pipeline, known_agents)
            if errors:
                raise HTTPException(status_code=422, detail=f"pipeline invalid: {', '.join(errors)}")

            run.pipeline_id = payload.pipeline_id
            pipeline_snapshot = pipeline.model_dump()

        run.pipeline_snapshot = pipeline_snapshot
        session.add(run)
        await session.commit()
        await session.refresh(run)

        await event_bus.publish(
            run.id,
            "run_created",
            {"idea": run.idea, "status": run.status},
        )
        await event_bus.publish(run.id, "run_updated", {"status": "queued"})

        # Enfileira e promove se houver vaga. O await garante que a resposta
        # reflete o status real (running se promoveu, queued se há run ativa).
        await _execute_pipeline_in_background(
            app,
            run_id=run.id,
            idea=run.idea,
            stack=run.stack,
            mock_llm=payload.mock_llm,
            routing_mode=payload.routing_mode,
            interactive=payload.interactive,
            model=payload.model,
            pipeline_snapshot=pipeline_snapshot,
        )
        await session.refresh(run)
        await _attach_pipeline_names([run], session)
        return run

    @app.post(
        "/api/v1/runs",
        response_model=RunResponse,
        status_code=201,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def create_run_v1(payload: RunCreate, session: AsyncSession = Depends(get_session)):
        """Rota canônica (M-18): cria e enfileira uma nova run."""
        return await _create_run_impl(payload, session)

    @app.get(
        "/api/v1/auth/me",
        response_model=AuthMeResponse,
        tags=["Auth"],
    )
    async def auth_me(principal: Principal = Depends(get_current_principal)) -> AuthMeResponse:
        """Identidade do principal (name + roles) — base do login da SPA."""
        return AuthMeResponse(name=principal.name, roles=list(principal.roles))

    @app.post(
        "/api/runs",
        response_model=RunResponse,
        status_code=201,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def create_run_legacy(
        payload: RunCreate,
        response: Response,
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de POST /api/v1/runs (M-18): delega e marca Sunset."""
        _mark_legacy(response)
        return await _create_run_impl(payload, session)

    @app.post(
        "/api/runs/{run_id}/execute",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def execute_run(
        run_id: str,
        session: AsyncSession = Depends(get_session),
    ):
        """Dispara a execução de uma pipeline pendente ou falhada em segundo plano."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        await _execute_pipeline_in_background(
            app,
            run_id=run.id,
            idea=run.idea,
            stack=run.stack,
        )

        return run

    async def _resume_run_impl(run_id: str, session: AsyncSession) -> PipelineRun:
        """Retoma uma execução interrompida usando o thread_id persistido (M-01).

        B5/B6: o resume NÃO roda mais fora da fila — passa pelo MESMO mecanismo
        E3 de run nova (_execute_pipeline_in_background, promovido até
        max_concurrent). O mock_llm é lido do CHECKPOINT (a run mock persiste
        `mock_llm=True` no estado; run real segue mock_llm=False) — antes o
        dispatcher de resume caía no default mock e gerava output falso.
        """
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        target_id = run.id
        # M-01/ADR-0003: usa o thread_id PERSISTIDO no PipelineRun (fonte
        # canônica), em vez de reconstruir 'project'/'run-{id}' à mão. Fallback
        # 'run-{id}' cobre runs recém-criadas cujo dispatch ainda não persistiu
        # a coluna (mesmo valor gravado por _promote_next/_execute_pipeline_in_background).
        thread_id = run.thread_id or f"run-{target_id}"

        # B5: mock_llm do checkpoint — runs reais (mock_llm=False persistido)
        # retomam SEM mock; runs originalmente mock seguem mock.
        checkpoint_state = await _checkpoint_state(thread_id)
        mock_llm = bool(checkpoint_state.get("mock_llm", False))

        # S3 T5 (round 1): resume usa o SNAPSHOT persistido da run (imutável),
        # nunca o template atual — se a run era de pipeline custom, o grafo
        # retomado é o mesmo do start (build_pipeline_graph); sem snapshot,
        # comportamento legado (build_graph default).
        await _execute_pipeline_in_background(
            app,
            run_id=target_id,
            idea=run.idea,
            stack=run.stack,
            mock_llm=mock_llm,
            routing_mode="full",
            interactive=False,
            model=None,
            pipeline_snapshot=run.pipeline_snapshot,
            resume=True,
        )
        await session.refresh(run)
        return run

    @app.post(
        "/api/v1/runs/{run_id}/resume",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def resume_run_v1(run_id: str, session: AsyncSession = Depends(get_session)):
        """Rota canônica (M-18): retoma do último checkpoint (thread_id persistido)."""
        return await _resume_run_impl(run_id, session)

    @app.post(
        "/api/runs/{run_id}/resume",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def resume_run_legacy(
        run_id: str,
        response: Response,
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de POST /api/v1/runs/{id}/resume (M-18)."""
        _mark_legacy(response)
        return await _resume_run_impl(run_id, session)

    async def _attach_pipeline_names(runs: list[PipelineRun], session: AsyncSession) -> list[PipelineRun]:
        """Popula `pipeline_name` nas runs (join com PipelineTemplate no read).

        Template deletado → pipeline_name None (snapshot preserva a execução).
        """
        ids = {r.pipeline_id for r in runs if r.pipeline_id}
        if not ids:
            return runs
        result = await session.execute(select(PipelineTemplate).where(PipelineTemplate.id.in_(ids)))
        names = {t.id: t.name for t in result.scalars().all()}
        for run in runs:
            run.pipeline_name = names.get(run.pipeline_id)  # type: ignore[attr-defined]
        return runs

    async def _list_runs_impl(skip: int, limit: int, session: AsyncSession) -> RunListResponse:
        """Lista execuções de pipeline com paginação (expoe status queued)."""
        total_query = select(func.count(PipelineRun.id))
        total_result = await session.execute(total_query)
        total = total_result.scalar_one()

        query = select(PipelineRun).order_by(PipelineRun.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        runs = list(result.scalars().all())

        await _attach_pipeline_names(runs, session)

        # Converte ORM -> RunResponse (from_attributes) explicitamente; o
        # response_model do FastAPI faria o mesmo em runtime.
        return RunListResponse(items=[RunResponse.model_validate(run) for run in runs], total=total)

    @app.get(
        "/api/v1/runs",
        response_model=RunListResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_runs_v1(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        session: AsyncSession = Depends(get_session),
    ):
        """Rota canônica (M-18): lista paginada de runs."""
        return await _list_runs_impl(skip, limit, session)

    @app.get(
        "/api/runs",
        response_model=RunListResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_runs_legacy(
        response: Response,
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de GET /api/v1/runs (M-18)."""
        _mark_legacy(response)
        return await _list_runs_impl(skip, limit, session)

    @app.get(
        "/api/v1/runs/queue",
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run_queue(session: AsyncSession = Depends(get_session)):
        """Estado da fila E3 (M-21): runs ativas + runs `queued` aguardando vaga.

        DECLARADA ANTES de GET /api/v1/runs/{run_id}: "queue" é path fixo e
        não pode ser capturada como run_id pelo roteador dinâmico.
        """
        q = app.state.run_queue
        pending_ids = list(q.pending)
        runs_by_id: dict[str, PipelineRun] = {}
        if pending_ids:
            result = await session.execute(select(PipelineRun).where(PipelineRun.id.in_(pending_ids)))
            runs_by_id = {run.id: run for run in result.scalars().all()}
        queued: list[dict] = []
        for run_id in pending_ids:
            run = runs_by_id.get(run_id)
            queued.append(
                {
                    "id": run_id,
                    "idea": run.idea if run else None,
                    "stack": run.stack if run else None,
                    "status": "queued",
                    "created_at": run.created_at if run else None,
                }
            )
        return {
            "max_concurrent": q.max_concurrent,
            "active_count": len(q.active),
            "active": sorted(q.active),
            "queued": queued,
        }

    async def _get_run_impl(run_id: str, session: AsyncSession) -> PipelineRun:
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        await _attach_pipeline_names([run], session)
        return run

    @app.get(
        "/api/v1/runs/{run_id}",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run_v1(run_id: str, session: AsyncSession = Depends(get_session)):
        """Rota canônica (M-18): detalhes de uma run."""
        return await _get_run_impl(run_id, session)

    @app.get(
        "/api/runs/{run_id}",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run_legacy(
        run_id: str,
        response: Response,
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de GET /api/v1/runs/{id} (M-18)."""
        _mark_legacy(response)
        return await _get_run_impl(run_id, session)

    @app.patch(
        "/api/runs/{run_id}",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def update_run(
        run_id: str,
        payload: RunUpdate,
        session: AsyncSession = Depends(get_session),
    ):
        """Atualiza campos de uma execução existente."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(run, field, value)

        await session.commit()
        await session.refresh(run)

        await ws_manager.broadcast(
            {
                "event": "run_updated",
                "run_id": run.id,
                "status": run.status,
                "current_node": run.current_node,
            }
        )

        return run

    @app.delete(
        "/api/runs/{run_id}",
        status_code=204,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def delete_run(run_id: str, session: AsyncSession = Depends(get_session)):
        """Remove uma execução de pipeline."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        await session.delete(run)
        await session.commit()

    async def _list_run_events_impl(run_id: str, after_seq: int, limit: int, session: AsyncSession) -> dict:
        """Backfill M-06: envelopes v1 persistidos da run, em ordem de seq."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        # Busca limit+1 para DETECTAR página cheia de verdade (has_more): a
        # heurística antiga (len == limit) marcava next_after_seq mesmo quando a
        # última página tinha EXATAMENTE limit eventos e não havia mais nada.
        raw = await event_bus.list_events(run_id, after_seq=after_seq, limit=limit + 1)
        events = raw[:limit]
        has_more = len(raw) > limit
        next_after_seq = events[-1]["seq"] if events and has_more else None
        return {"run_id": run_id, "events": events, "next_after_seq": next_after_seq}

    @app.get(
        "/api/v1/runs/{run_id}/events",
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_run_events_v1(
        run_id: str,
        after_seq: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=1000),
        session: AsyncSession = Depends(get_session),
    ):
        """Rota canônica (M-06): backfill de eventos persistidos da run."""
        return await _list_run_events_impl(run_id, after_seq, limit, session)

    @app.get(
        "/api/runs/{run_id}/events",
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_run_events_legacy(
        run_id: str,
        response: Response,
        after_seq: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=1000),
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de GET /api/v1/runs/{id}/events (M-18)."""
        _mark_legacy(response)
        return await _list_run_events_impl(run_id, after_seq, limit, session)

    async def _get_run_timeline_impl(run_id: str, after_seq: int, limit: int, session: AsyncSession) -> dict:
        """Timeline C5/M-02: eventos do journal + checkpoints LangGraph da run."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return await event_bus.get_timeline(run_id, after_seq=after_seq, limit=limit)

    @app.get(
        "/api/v1/runs/{run_id}/timeline",
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run_timeline_v1(
        run_id: str,
        after_seq: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        session: AsyncSession = Depends(get_session),
    ):
        """Rota canônica (M-02): timeline unificada (eventos + checkpoints) da run."""
        return await _get_run_timeline_impl(run_id, after_seq, limit, session)

    @app.get(
        "/api/runs/{run_id}/timeline",
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run_timeline_legacy(
        run_id: str,
        response: Response,
        after_seq: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de GET /api/v1/runs/{id}/timeline (M-18)."""
        _mark_legacy(response)
        return await _get_run_timeline_impl(run_id, after_seq, limit, session)

    async def _record_decision_impl(
        run_id: str, payload: HumanDecisionCreate, session: AsyncSession
    ) -> HumanDecisionModel:
        """Registra decisão humana (HITL) vinda da Web Dashboard UI ou CLI.

        A1 (B1): valida a decisão ANTES de gravar — run existe (404), run em
        status que aceita decisão (running/paused com gate pendente) e
        gate_node com gate REALMENTE pendente no checkpoint (409). Sem isso o
        POST /decide aceitava qualquer coisa e poluía o audit trail.
        """
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        if run.status not in ("running", "paused"):
            raise HTTPException(
                status_code=409,
                detail=f"run {run_id} não aceita decisões no status '{run.status}'",
            )

        # B1(c): gate_node precisa casar com um gate PENDENTE de verdade — o
        # checkpoint da thread parado em interrupt com o nó no `next`, e a run
        # INTERATIVA (is_interactive no checkpoint). Run não-interativa em voo
        # tem next transitório mas não aguarda decisão humana (flake A1).
        thread_id = run.thread_id or f"run-{run.id}"
        pending, is_interactive = await _checkpoint_gate_state(thread_id)
        if not is_interactive or payload.gate_node not in pending:
            raise HTTPException(
                status_code=409,
                detail=f"no pending decision for gate_node {payload.gate_node} on run {run_id}",
            )

        # B2: garante state_patch/consumed ANTES do INSERT (o ORM pode não
        # declarar as colunas em DBs legados — o dispatcher filtra por consumed).
        _ensure_human_decisions_state_patch_column(_telemetry_db_path())

        decision = HumanDecisionModel(
            run_id=run_id,
            gate_node=payload.gate_node,
            action=payload.action,
            feedback_category=payload.feedback_category,
            feedback_message=payload.feedback_message,
            user=payload.user,
        )
        session.add(decision)
        if payload.state_patch is not None:
            # C3 (M-12) action=adjust_state: persiste o state_patch na coluna
            # aditiva (fora do ORM) no MESMO commit do INSERT — flush + UPDATE
            # na mesma transação. Atomicidade é obrigatória: o polling do gate
            # roda a cada 0.5s e, se a linha fosse visível com state_patch NULL
            # antes do UPDATE, a decisão era consumida sem o patch (race real).
            await session.flush()  # atribui decision.id (default _generate_uuid)
            await session.execute(
                text("UPDATE human_decisions SET state_patch = :sp WHERE id = :id"),
                {"sp": json.dumps(payload.state_patch, ensure_ascii=False), "id": decision.id},
            )
        await session.commit()
        await session.refresh(decision)

        # Emite evento via EventBus (persiste + broadcast) para notificar o
        # TaskDispatcher ou UI — M-06: só o EventBus publica no canal do run.
        event_payload: dict = {
            "gate_node": decision.gate_node,
            "action": decision.action,
            "feedback_category": decision.feedback_category,
            "feedback_message": decision.feedback_message,
            "user": decision.user,
        }
        if payload.state_patch is not None:
            event_payload["state_patch"] = payload.state_patch
        await event_bus.publish(run_id, "human_decision_submitted", event_payload)

        return decision

    @app.post(
        "/api/v1/runs/{run_id}/decide",
        response_model=HumanDecisionResponse,
        status_code=201,
        tags=["Human-in-the-Loop"],
        dependencies=[Depends(verify_authentication)],
    )
    async def record_human_decision_v1(
        run_id: str,
        payload: HumanDecisionCreate,
        session: AsyncSession = Depends(get_session),
    ):
        """Rota canônica (M-18): registra decisão humana para a run."""
        return await _record_decision_impl(run_id, payload, session)

    @app.post(
        "/api/runs/{run_id}/decide",
        response_model=HumanDecisionResponse,
        status_code=201,
        tags=["Human-in-the-Loop"],
        dependencies=[Depends(verify_authentication)],
    )
    async def record_human_decision_legacy(
        run_id: str,
        payload: HumanDecisionCreate,
        response: Response,
        session: AsyncSession = Depends(get_session),
    ):
        """Alias legado de POST /api/v1/runs/{id}/decide (M-18)."""
        _mark_legacy(response)
        return await _record_decision_impl(run_id, payload, session)

    async def _cancel_run_impl(run_id: str, session: AsyncSession) -> PipelineRun:
        """Cancela uma run (C8): queued → remove da fila; running → cancela a
        task; paused → failed. completed/failed → 409 (não cancelável)."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        if run.status in ("completed", "failed"):
            raise HTTPException(status_code=409, detail="run not cancellable")

        q = app.state.run_queue
        async with q.lock:
            if run_id in q.pending:
                # Remove da fila FIFO preservando a ordem das demais.
                q.pending = deque(rid for rid in q.pending if rid != run_id)
                q.params.pop(run_id, None)
            q.active.discard(run_id)

        # C8: cancela a task asyncio correspondente (se em execução). O finally
        # de _run_pipeline libera a vaga e promove a próxima da fila.
        task = getattr(app.state, "run_tasks", {}).get(run_id)
        if task is not None and not task.done():
            task.cancel()

        run.status = "failed"
        run.logs = "Cancelado pelo usuário"
        await session.commit()
        await session.refresh(run)

        # Emite run_updated com o status final para o frontend (WS) atualizar
        # em tempo real — mesmo mecanismo do _set_run_status.
        await event_bus.publish(
            run_id,
            "run_updated",
            {"status": "failed", "reason": "cancelado pelo usuário"},
        )
        return run

    @app.post(
        "/api/v1/runs/{run_id}/cancel",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def cancel_run_v1(run_id: str, session: AsyncSession = Depends(get_session)):
        """Rota canônica (C8): cancela uma run (queued/running/paused)."""
        return await _cancel_run_impl(run_id, session)

    @app.get(
        "/api/v1/runs/{run_id}/decisions",
        response_model=list[HumanDecisionResponse],
        tags=["Human-in-the-Loop"],
        dependencies=[Depends(verify_authentication)],
    )
    @app.get(
        "/api/runs/{run_id}/decisions",
        response_model=list[HumanDecisionResponse],
        tags=["Human-in-the-Loop"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_human_decisions(
        run_id: str,
        session: AsyncSession = Depends(get_session),
    ):
        """Lista todo o histórico de decisões humanas (HITL) para uma execução.

        Bug 2 (fix): o front ADE chama ``/api/v1/runs/{id}/decisions``; o
        decorator v1 (canônico) e o legado ``/api/runs/...`` compartilham a
        MESMA implementação (padrão M-18 dos demais aliases v1/legado).
        """
        from sqlalchemy import select

        result = await session.execute(
            select(HumanDecisionModel)
            .where(HumanDecisionModel.run_id == run_id)
            .order_by(HumanDecisionModel.timestamp.asc())
        )
        decisions = result.scalars().all()
        return decisions

    # ─── Endpoints da Trilogia Agentic ──────────────────────────────
    @app.get("/api/genome", tags=["Trilogia Agentic"])
    async def get_genome_info():
        """Retorna metadados, AST e métricas de dependência do Codebase Genome."""
        try:
            from genome import GenomeScanner

            scanner = GenomeScanner(".")
            g = scanner.scan()
            return g.model_dump()
        except Exception as e:
            return {"error": str(e), "modules": [], "bus_factor": 1.0}

    @app.get("/api/registry", tags=["Trilogia Agentic"])
    async def get_registry_info():
        """Retorna contratos de interface rastreados e quebras detectadas pelo Agentic Registry."""
        try:
            from registry import RegistryChecker

            checker = RegistryChecker(".")
            breaking = checker.check()
            return {
                "breaking_changes": [b.model_dump() for b in breaking],
                "status": "ok" if not breaking else "warning",
            }
        except Exception as e:
            return {"error": str(e), "breaking_changes": []}

    @app.get("/api/retro", tags=["Trilogia Agentic"])
    async def get_retro_info():
        """Retorna histórico de sessões, causas-raiz e recomendações do Agentic Retro."""
        try:
            from retro import RetroStore, SessionAnalyzer

            store = RetroStore()
            sessions = store.list_sessions(limit=5)
            analyzer = SessionAnalyzer()
            learnings = analyzer.extract_learnings()
            return {
                "sessions_count": len(sessions),
                "learnings": [item.model_dump() for item in learnings],
            }
        except Exception as e:
            return {"error": str(e), "learnings": []}

    # ─── Trajectories (ADE Fase 1) ───────────────────────────────────
    from lf.api.trajectories import trajectories_router

    app.include_router(trajectories_router)

    # ─── MCP (ADE Fase 1) ────────────────────────────────────────────
    from lf.api.mcp import mcp_router

    app.include_router(mcp_router)

    # ─── Providers (ADE Fase 1) ──────────────────────────────────────
    from lf.api.providers import providers_router

    app.include_router(providers_router)

    # ─── Config API (ADE Fase 1) ─────────────────────────────────────
    # Auth aplicada no include (config.py não importa auth no módulo para
    # evitar ciclo: auth.py importa APISettings deste módulo — M-03).
    from lf.api.config import config_router

    app.include_router(config_router, dependencies=[Depends(verify_authentication)])

    # ─── Costs (Fase A, n4 — M-08/M-10) ──────────────────────────────
    from lf.api.costs import costs_router

    app.include_router(costs_router, dependencies=[Depends(verify_authentication)])

    # ─── Memory (ADE — MemoryPanel) ──────────────────────────────────
    from lf.api.memory import memory_router

    app.include_router(memory_router, dependencies=[Depends(verify_authentication)])

    # ─── Evals (ADE — EvalsPanel) ────────────────────────────────────
    from lf.api.evals import evals_router

    app.include_router(evals_router, dependencies=[Depends(verify_authentication)])

    # ─── Git (ADE — GitPanel) ─────────────────────────────────────────
    from lf.api.git import git_router

    app.include_router(git_router, dependencies=[Depends(verify_authentication)])

    # ─── Prompts (ADE — PromptPanel) ──────────────────────────────────
    from lf.api.prompts import prompts_router

    app.include_router(prompts_router, dependencies=[Depends(verify_authentication)])

    # ─── Artifacts (SPA InspectDrawer) ────────────────────────────────
    from lf.api.artifacts import artifacts_router

    app.include_router(artifacts_router, dependencies=[Depends(verify_authentication)])

    # ─── Terminal & Command Runner (ADE) ───────────────────────────────
    from lf.api.terminal import terminal_router

    app.include_router(terminal_router, dependencies=[Depends(verify_authentication)])

    # ─── AST & Dependency Analysis (ADE) ──────────────────────────────
    from lf.api.ast_analyzer import ast_router

    app.include_router(ast_router, dependencies=[Depends(verify_authentication)])

    # ─── Code Coverage & Metrics (ADE) ────────────────────────────────
    from lf.api.coverage import coverage_router

    app.include_router(coverage_router, dependencies=[Depends(verify_authentication)])

    # ─── Docker & Devcontainer Generation (ADE) ───────────────────────
    from lf.api.docker_gen import docker_router

    app.include_router(docker_router, dependencies=[Depends(verify_authentication)])

    # ─── Agents (S2 — CRUD de agentes) ─────────────────────────────────
    from lf.api.agents import agents_router

    app.include_router(agents_router, dependencies=[Depends(verify_authentication)])

    # ─── Pipelines (S3 — editor de pipelines) ──────────────────────────
    from lf.api.pipelines import pipelines_router

    app.include_router(pipelines_router, dependencies=[Depends(verify_authentication)])

    # ─── SPA React (M-16/B4) ─────────────────────────────────────────
    # Monta o dist da SPA em /app se disponível (env LF_SPA_DIST ou pacote
    # embutido lf.ade.static.dist na B5); sem dist, apenas loga warning.
    mount_spa(app)

    return app


async def _set_run_status(run_id: str, status: str, **extra) -> None:
    """Persiste o status (e campos extras) do PipelineRun e publica run_updated (M-21)."""
    from lf.api.database import session_factory
    from lf.api.models import PipelineRun

    if session_factory:
        async with session_factory() as session:
            run = await session.get(PipelineRun, run_id)
            if run:
                run.status = status
                for key, value in extra.items():
                    setattr(run, key, value)
                await session.commit()
    # D12: degraded/degraded_reason chegam no payload do run_updated (aditivo)
    # — o frontend (que escuta WS) atualiza o badge de degradação em tempo real.
    payload: dict = {"status": status}
    if "degraded" in extra:
        payload["degraded"] = bool(extra["degraded"])
    if extra.get("degraded_reason") is not None:
        payload["degraded_reason"] = extra["degraded_reason"]
    await event_bus.publish(run_id, "run_updated", payload)


async def _promote_next(app: FastAPI) -> None:
    """Promove runs enfileiradas (FIFO) para `running` enquanto houver vaga.

    M-21 (E3): até ``max_concurrent`` runs ativas em paralelo — promove de uma
    vez todas as que couberem no limite. A execução roda em background e, no
    término (finally em `_run_pipeline`), chama `_promote_next` de novo para
    liberar o próximo slot.
    """
    q = app.state.run_queue
    promoted: list[tuple[str, dict]] = []
    async with q.lock:
        while len(q.active) < q.max_concurrent and q.pending:
            run_id = q.pending.popleft()
            q.active.add(run_id)
            promoted.append((run_id, q.params.pop(run_id, {})))

    for run_id, params in promoted:
        idea = params.get("idea", "")
        stack = params.get("stack", "python")
        mock_llm = params.get("mock_llm", False)
        routing_mode = params.get("routing_mode", "full")
        interactive = params.get("interactive", False)
        model = params.get("model")
        pipeline_snapshot = params.get("pipeline_snapshot")
        # B6: resume entra na fila E3 como run nova (resume=True sinaliza ao
        # executor para chamar dispatcher.resume em vez de dispatch).
        resume = params.get("resume", False)

        # M-02/ADR-0003: thread canônica `run-{id}` persistida junto da promoção.
        await _set_run_status(run_id, "running", thread_id=f"run-{run_id}", parent_run_id=run_id)

        task = asyncio.create_task(
            _run_pipeline(
                app,
                run_id=run_id,
                idea=idea,
                stack=stack,
                mock_llm=mock_llm,
                routing_mode=routing_mode,
                interactive=interactive,
                model=model,
                pipeline_snapshot=pipeline_snapshot,
                resume=resume,
            )
        )
        # C8: registry run_id → asyncio.Task para o POST /cancel cancelar a
        # execução correspondente (a fila em memória morre no restart, ok).
        app.state.run_tasks[run_id] = task
        task.add_done_callback(lambda t, rid=run_id: app.state.run_tasks.pop(rid, None))


async def _execute_pipeline_in_background(
    app: FastAPI,
    run_id: str,
    idea: str,
    stack: str,
    mock_llm: bool = False,
    routing_mode: str = "full",
    interactive: bool = False,
    model: str | None = None,
    pipeline_snapshot: dict | None = None,
    resume: bool = False,
) -> None:
    """Enfileira a run na fila E3 (FIFO) e dispara a promoção se houver vaga.

    M-21 (E3): runs novas nascem `queued` e só executam quando houver slot
    livre (até ``max_concurrent`` simultâneas).
    Idempotente: uma run já ativa/enfileirada não é enfileirada de novo.
    B6: resume usa o MESMO caminho (``resume=True`` → o executor chama
    dispatcher.resume em vez de dispatch).
    """
    q = app.state.run_queue
    async with q.lock:
        if run_id in q.active or run_id in q.pending:
            return
        q.params[run_id] = {
            "idea": idea,
            "stack": stack,
            "mock_llm": mock_llm,
            "routing_mode": routing_mode,
            "interactive": interactive,
            "model": model,
            "pipeline_snapshot": pipeline_snapshot,
            "resume": resume,
        }
        q.pending.append(run_id)
    await _promote_next(app)


async def _checkpoint_next_nodes(thread_id: str) -> list[str]:
    """Nós PENDENTES do checkpoint da thread (vazio = run terminou).

    M-10: o hard-stop de budget PAUSA o grafo via ``interrupt()`` do LangGraph
    (developer.py) — a run NÃO falha; o checkpoint fica com ``next != []``
    (pendente no nó que interrompeu). Verificado empiricamente: o dispatch NÃO
    expõe ``__interrupt__`` no estado retornado (``state_snapshot.values`` não
    o contém), então a detecção confiável é consultar o saver (trajectories.db).
    """
    from pathlib import Path

    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    db_path = Path(".loopforge/trajectories.db").resolve()
    if not db_path.exists():
        return []
    saver = create_async_checkpointer(db_path)
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return list(snap.next) if snap else []
    except Exception:
        return []
    finally:
        await saver.conn.close()


async def _checkpoint_state(thread_id: str) -> dict:
    """Valores do checkpoint da thread (dict vazio se inexistente/inacessível).

    B5: o resume lê `mock_llm` (e demais canais) do estado persistido — a run
    mock grava `mock_llm=True` no initial_state e o checkpoint preserva.
    """
    from pathlib import Path

    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    db_path = Path(".loopforge/trajectories.db").resolve()
    if not db_path.exists():
        return {}
    saver = create_async_checkpointer(db_path)
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return dict(snap.values) if snap and snap.values else {}
    except Exception:
        return {}
    finally:
        await saver.conn.close()


async def _checkpoint_gate_state(thread_id: str) -> tuple[list[str], bool]:
    """(next, is_interactive) do checkpoint da thread (B1 refinado).

    Gate REALMENTE pendente exige run INTERATIVA parada em interrupt — uma run
    não-interativa em voo tem `next != []` transitório (ex.: next=[qa] entre
    developer e qa) mas NÃO está aguardando decisão humana; aceitar decisão aí
    era o flake do contrato A1 (201 em vez de 409).
    """
    from pathlib import Path

    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    db_path = Path(".loopforge/trajectories.db").resolve()
    if not db_path.exists():
        return [], False
    saver = create_async_checkpointer(db_path)
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        if not snap:
            return [], False
        values = dict(snap.values or {})
        return list(snap.next), bool(values.get("is_interactive", False))
    except Exception:
        return [], False
    finally:
        await saver.conn.close()


async def _pipeline_context_from_snapshot(
    snapshot: dict | None,
) -> tuple[PipelineBase | None, dict]:
    """Monta (pipeline, agent_templates) a partir do snapshot persistido da run.

    S3 T5 (round 1): fonte ÚNICA do pipeline para create E resume — o snapshot
    é imutável por run; o template atual NUNCA é usado em execução. Templates da
    biblioteca são resolvidos na execução; se o agente foi deletado depois do
    snapshot, o build levanta ValueError('unknown agent node') → o try/except
    do executor converte em run failed com log claro.
    """
    from lf.api.agents import AgentBase
    from lf.api.database import session_factory

    if not snapshot:
        return None, {}

    pipeline = PipelineBase(**snapshot)
    agent_templates: dict[str, AgentBase] = {}
    if session_factory:
        async with session_factory() as bg_session:
            agents = await bg_session.execute(select(AgentTemplate))
            for row in agents.scalars().all():
                agent_templates[row.id] = AgentBase(
                    name=row.name,
                    description=row.description,
                    prompt=row.prompt,
                    model=row.model,
                    temperature=row.temperature,
                    max_retries=row.max_retries,
                    timeout_seconds=row.timeout_seconds,
                    env_vars=row.env_vars,
                    tools_allowlist=row.tools_allowlist,
                    permissions=row.permissions,
                    stack=row.stack,
                    budget_usd=row.budget_usd,
                )
    return pipeline, agent_templates


async def _run_pipeline(
    app: FastAPI,
    run_id: str,
    idea: str,
    stack: str,
    mock_llm: bool = False,
    routing_mode: str = "full",
    interactive: bool = False,
    model: str | None = None,
    pipeline_snapshot: dict | None = None,
    resume: bool = False,
) -> None:
    """Executa a pipeline de uma run JÁ promovida; no fim, promove a próxima da fila.

    B6: resume=True chama ``dispatcher.resume`` (thread persistida) em vez de
    ``dispatch`` — o gate HITL pendente é re-entrado dentro do resume.
    """
    import os
    import time

    from lf.config.schema import TaskSchema
    from lf.orchestrator.task_dispatcher import TaskDispatcher

    start_time = time.time()

    # B6: thread canônica para o resume — a persistida em pipeline_runs
    # (fallback `run-{id}`, mesmo valor gravado na promoção).
    resume_thread_id: str | None = None
    if resume:
        from lf.api.database import session_factory

        if session_factory:
            async with session_factory() as s:
                run_row = await s.get(PipelineRun, run_id)
                if run_row:
                    resume_thread_id = run_row.thread_id or f"run-{run_id}"

    task = TaskSchema(
        id=f"task-{run_id[:8]}",
        title=idea,
        agent_id="cpo",
        stack=stack,
        # routing_mode chega como str dos params da fila (payload da API); o
        # próprio TaskSchema valida o Literal em runtime — cast só tipográfico.
        routing_mode=cast(Literal["full", "fast", "patch", "review-only", "explore"], routing_mode),
        model=model,
    )

    project_dir = f"/tmp/loopforge/run_{run_id}"
    os.makedirs(project_dir, exist_ok=True)

    if os.getenv("LF_API_TEST"):
        mock_llm = True

    # S3 (editor de pipelines): se a run tem pipeline_snapshot (imutável do
    # start), monta o grafo custom via build_pipeline_graph; senão segue o
    # fluxo atual (build_graph default). Agent templates da biblioteca são
    # resolvidos na EXECUÇÃO: se o agente foi deletado depois do snapshot, o
    # build lança ValueError('unknown agent node') → cai no except abaixo →
    # run failed com erro claro no log (nunca crash silencioso).
    pipeline, agent_templates = await _pipeline_context_from_snapshot(pipeline_snapshot)

    dispatcher = TaskDispatcher(
        mock_llm=mock_llm,
        interactive=interactive,
        notify=False,
        pipeline=pipeline,
        agent_templates=agent_templates,
    )

    def _sync_dispatch():
        if resume:
            return dispatcher.resume(thread_id=resume_thread_id or f"run-{run_id}")
        return dispatcher.dispatch(
            task,
            project_id=f"run-{run_id}",
            shared_state={"project_dir": project_dir, "output_dir": project_dir},
        )

    try:
        final_state = await asyncio.to_thread(_sync_dispatch)
        duration = round(time.time() - start_time, 2)

        err = final_state.get("error")
        test_report = final_state.get("test_report", {})
        tests_failed = test_report.get("summary", {}).get("tests_failed", 0) if isinstance(test_report, dict) else 0

        final_status = "completed" if (not err and tests_failed == 0) else "failed"
        current_node = final_state.get("next_agent", "FINISH")
        if resume:
            log_msg = err if err else f"Pipeline retomada com sucesso em {duration}s. Testes com falha: {tests_failed}"
        else:
            log_msg = err if err else f"Pipeline concluída em {duration}s. Testes com falha: {tests_failed}"

        # M-10: hard-stop de budget = PAUSA (interrupt no grafo) — detecta pelo
        # checkpoint com next != [] (mecanismo documentado em
        # _checkpoint_next_nodes). NÃO quebra o caminho normal (completed) nem
        # o de erro (failed): só o caminho "success" passa pela checagem.
        if final_status == "completed" and not err:
            pending = await _checkpoint_next_nodes(f"run-{run_id}")
            if pending:
                final_status = "paused"
                current_node = pending[0]
                log_msg = (
                    f"Run pausada no nó {pending[0]} (budget excedido) — use POST /cost/override + /resume para retomar"
                )

        # Persistência do estado degradado (mock fallback, provider degradado)
        # no PipelineRun — GET /runs devolve via from_attributes.
        degraded = bool(final_state.get("degraded"))
        degraded_reason = final_state.get("degraded_reason")
        if not isinstance(degraded_reason, str):
            degraded_reason = None
        # B7: no resume o checkpoint pode não carregar degraded (a run pausada
        # persistiu a flag no DB) — preserva os valores persistidos quando o
        # estado retornado não os declara.
        if resume and not degraded:
            from lf.api.database import session_factory as _sf

            if _sf:
                async with _sf() as _s:
                    _r = await _s.get(PipelineRun, run_id)
                    if _r and _r.degraded:
                        degraded = True
                        degraded_reason = degraded_reason or _r.degraded_reason

        await _set_run_status(
            run_id,
            final_status,
            current_node=current_node,
            duration_seconds=duration,
            logs=log_msg,
            degraded=degraded,
            degraded_reason=degraded_reason,
        )

        await event_bus.publish(
            run_id,
            "pipeline_finished",
            {
                "status": final_status,
                "duration_seconds": duration,
            },
        )

        # Evento do snapshot do CircuitBreaker (10 campos) — consumido pela UI
        # para renderizar o estado do gate de custo/falhas da run. M3: transições
        # são publicadas EM TEMPO REAL pelo dispatcher (_publish_cb_transition);
        # este finally fica como fallback idempotente — só publica se o estado
        # final ainda não foi emitido durante a execução (sem duplicata).
        cb = final_state.get("circuit_breaker")
        if isinstance(cb, dict) and cb.get("state") != getattr(dispatcher, "_published_cb_state", None):
            await event_bus.publish(run_id, "circuit_breaker_changed", cb)
    except Exception as e:
        error = str(e)
        duration = round(time.time() - start_time, 2)
        # Traceback no log (item 1): a causa raiz da falha da run não pode
        # depender do GET /runs/{id}/logs — o operador precisa do stack.
        logger.exception("Erro na execução da pipeline (run_id=%s)", run_id)
        await _set_run_status(
            run_id,
            "failed",
            duration_seconds=duration,
            logs=f"Erro na execução da pipeline: {error}",
        )
        await event_bus.publish(
            run_id,
            "pipeline_error",
            {"error": error},
        )
    finally:
        # B6 (corrida fechada): libera a vaga e promove a próxima da fila (FIFO)
        # ANTES de o status terminal ficar visível no GET — o resume via fila
        # via ficar no-op se a run ainda estivesse em q.active quando o GET
        # observasse o status final (corrida resume × finally).
        q = app.state.run_queue
        async with q.lock:
            q.active.discard(run_id)
        await _promote_next(app)
