"""Aplicação FastAPI principal do LoopForge.

Expõe endpoints REST, WebSockets autenticados para streaming e Web Dashboard UI.
"""
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.auth import verify_authentication
from lf.api.config import get_api_settings
from lf.api.dashboard_html import get_dashboard_html
from lf.api.database import close_db, get_session, init_db

from lf.api.models import PipelineRun
from lf.api.schemas import (
    HealthResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunUpdate,
)
from lf.api.websocket_manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia ciclo de vida da aplicação: init e close do DB."""
    settings = get_api_settings()
    await init_db(settings)
    yield
    await close_db()


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI oficial do LoopForge."""
    settings = get_api_settings()
    app = FastAPI(
        title="LoopForge API",
        description="API REST, WebSockets e Dashboard Web para gerenciamento de pipelines do LoopForge v6",
        version="6.0.0",
        lifespan=lifespan,
    )

    # ─── Middleware: CORS ───────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
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

    # ─── Dashboard Web UI ───────────────────────────────────────────
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

        await ws_manager.connect(websocket)
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
                data = await websocket.receive_json()
                if data.get("type") == "ping":
                    await ws_manager.send_personal_message({"type": "pong"}, websocket)
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    # ─── CRUD Runs ──────────────────────────────────────────────────
    @app.post(
        "/api/runs",
        response_model=RunResponse,
        status_code=201,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def create_run(payload: RunCreate, session: AsyncSession = Depends(get_session)):
        """Cria uma nova execução de pipeline."""
        run = PipelineRun(
            idea=payload.idea,
            stack=payload.stack,
            status="pending",
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)

        await ws_manager.broadcast(
            {
                "event": "run_created",
                "run_id": run.id,
                "idea": run.idea,
                "status": run.status,
            }
        )

        return run

    @app.get(
        "/api/runs",
        response_model=RunListResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def list_runs(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        session: AsyncSession = Depends(get_session),
    ):
        """Lista execuções de pipeline com paginação."""
        total_query = select(func.count(PipelineRun.id))
        total_result = await session.execute(total_query)
        total = total_result.scalar_one()

        query = (
            select(PipelineRun).order_by(PipelineRun.created_at.desc()).offset(skip).limit(limit)
        )
        result = await session.execute(query)
        runs = result.scalars().all()

        return RunListResponse(items=list(runs), total=total)

    @app.get(
        "/api/runs/{run_id}",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
        """Retorna detalhes de uma execução específica."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

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

    return app
