"""Aplicação FastAPI principal do LoopForge.

Expõe endpoints REST para gerenciar execuções de pipeline (runs).
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lf.contrib.api.config import APISettings
from lf.contrib.api.dashboard_html import DASHBOARD_HTML
from lf.contrib.api.database import close_db, get_session, init_db
from lf.contrib.api.models import PipelineRun
from lf.contrib.api.schemas import (
    HealthResponse,
    RunCreate,
    RunListResponse,
    RunResponse,
    RunUpdate,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia ciclo de vida da aplicação: init e close do DB."""
    settings = APISettings()
    await init_db(settings)
    yield
    await close_db()


def create_app() -> FastAPI:
    """Factory da aplicação FastAPI."""
    app = FastAPI(
        title="LoopForge API",
        description="API REST e Dashboard Web para gerenciamento de pipelines do LoopForge",
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


    # ─── CRUD Runs ──────────────────────────────────────────────────
    @app.post("/api/runs", response_model=RunResponse, status_code=201, tags=["Runs"])
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
        return run

    @app.get("/api/runs", response_model=RunListResponse, tags=["Runs"])
    async def list_runs(
        skip: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        session: AsyncSession = Depends(get_session),
    ):
        """Lista execuções de pipeline com paginação."""
        total_query = select(func.count(PipelineRun.id))
        total_result = await session.execute(total_query)
        total = total_result.scalar_one()

        query = select(PipelineRun).order_by(PipelineRun.created_at.desc()).offset(skip).limit(limit)
        result = await session.execute(query)
        runs = result.scalars().all()

        return RunListResponse(items=runs, total=total)

    @app.get("/api/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
    async def get_run(run_id: str, session: AsyncSession = Depends(get_session)):
        """Retorna detalhes de uma execução específica."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.patch("/api/runs/{run_id}", response_model=RunResponse, tags=["Runs"])
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
        return run

    @app.delete("/api/runs/{run_id}", status_code=204, tags=["Runs"])
    async def delete_run(run_id: str, session: AsyncSession = Depends(get_session)):
        """Remove uma execução de pipeline."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        await session.delete(run)
        await session.commit()

    return app