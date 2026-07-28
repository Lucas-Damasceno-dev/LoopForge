"""Aplicação FastAPI principal do LoopForge.

Expõe endpoints REST, WebSockets para streaming em tempo real e Web Dashboard UI.
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.auth import verify_authentication
from lf.api.config import APISettings
from lf.api.dashboard_html import DASHBOARD_HTML
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
    settings = APISettings()
    await init_db(settings)
    yield
    await close_db()


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI oficial do LoopForge."""
    app = FastAPI(
        title="LoopForge API",
        description="API REST, WebSockets e Dashboard Web para gerenciamento de pipelines do LoopForge v6",
        version="6.0.0",
        lifespan=lifespan,
    )

    # ─── Dashboard Web UI ───────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    async def render_dashboard():
        """Serves the modern Glassmorphic Web Dashboard UI."""
        return HTMLResponse(content=DASHBOARD_HTML)

    # ─── Health ─────────────────────────────────────────────────────
    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        """Verifica se a API e o banco estão operacionais."""
        return HealthResponse()

    # ─── WebSockets para Streaming em Tempo Real ────────────────────
    @app.websocket("/ws/streaming")
    @app.websocket("/ws/runs/{run_id}")
    async def websocket_endpoint(websocket: WebSocket, run_id: str | None = None):
        """Conexão WebSocket para streaming de nós e eventos de pipeline em tempo real."""
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
