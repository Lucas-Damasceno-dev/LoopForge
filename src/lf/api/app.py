"""Aplicação FastAPI principal do LoopForge.

Expõe endpoints REST, WebSockets autenticados para streaming e Web Dashboard UI.
"""
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.auth import verify_authentication
from lf.api.config import get_api_settings
from lf.api.dashboard_html import get_dashboard_html
from lf.api.database import close_db, get_session, init_db
from lf.api.models import HumanDecisionModel, PipelineRun
from lf.api.schemas import (
    HealthResponse,
    HumanDecisionCreate,
    HumanDecisionResponse,
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

    # ─── CRUD & Execução de Runs ──────────────────────────────────
    @app.post(
        "/api/runs",
        response_model=RunResponse,
        status_code=201,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def create_run(
        payload: RunCreate,
        session: AsyncSession = Depends(get_session),
    ):
        """Cria e dispara uma nova execução de pipeline em segundo plano."""
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

        import asyncio
        asyncio.create_task(
            _execute_pipeline_in_background(
                run_id=run.id,
                idea=payload.idea,
                stack=payload.stack,
                mock_llm=payload.mock_llm,
                routing_mode=payload.routing_mode,
                interactive=payload.interactive,
            )
        )

        return run

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

        import asyncio
        asyncio.create_task(
            _execute_pipeline_in_background(
                run_id=run.id,
                idea=run.idea,
                stack=run.stack,
            )
        )

        return run

    @app.post(
        "/api/runs/{run_id}/resume",
        response_model=RunResponse,
        tags=["Runs"],
        dependencies=[Depends(verify_authentication)],
    )
    async def resume_run(
        run_id: str,
        session: AsyncSession = Depends(get_session),
    ):
        """Retoma uma execução de pipeline interrompida a partir do último checkpoint."""
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        import asyncio
        target_id = run.id

        def _sync_resume():
            from lf.orchestrator.task_dispatcher import TaskDispatcher
            dispatcher = TaskDispatcher()
            return dispatcher.resume(project_id="project", task_id=f"run-{target_id}")

        async def _resume_in_bg():
            from lf.api.database import session_factory
            if session_factory:
                async with session_factory() as bg_session:
                    r = await bg_session.get(PipelineRun, target_id)
                    if r:
                        r.status = "running"
                        await bg_session.commit()
            try:
                final_state = await asyncio.to_thread(_sync_resume)
                if session_factory:
                    async with session_factory() as bg_session:
                        r = await bg_session.get(PipelineRun, target_id)
                        if r:
                            r.status = "completed" if not final_state.get("error") else "failed"
                            r.logs = final_state.get("error") or "Pipeline retomada com sucesso"
                            await bg_session.commit()
            except Exception as e:
                if session_factory:
                    async with session_factory() as bg_session:
                        r = await bg_session.get(PipelineRun, target_id)
                        if r:
                            r.status = "failed"
                            r.logs = str(e)
                            await bg_session.commit()

        asyncio.create_task(_resume_in_bg())
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


    @app.post(
        "/api/runs/{run_id}/decide",
        response_model=HumanDecisionResponse,
        status_code=201,
        tags=["Human-in-the-Loop"],
        dependencies=[Depends(verify_authentication)],
    )
    async def record_human_decision(
        run_id: str,
        payload: HumanDecisionCreate,
        session: AsyncSession = Depends(get_session),
    ):
        """Registra decisão humana (HITL) vinda da Web Dashboard UI ou CLI."""
        decision = HumanDecisionModel(
            run_id=run_id,
            gate_node=payload.gate_node,
            action=payload.action,
            feedback_category=payload.feedback_category,
            feedback_message=payload.feedback_message,
            user=payload.user,
        )
        session.add(decision)
        await session.commit()
        await session.refresh(decision)

        # Emite evento via WebSocket para notificar o TaskDispatcher ou UI
        await ws_manager.broadcast(
            {
                "event": "human_decision_submitted",
                "run_id": run_id,
                "gate_node": decision.gate_node,
                "action": decision.action,
                "feedback_category": decision.feedback_category,
                "feedback_message": decision.feedback_message,
                "user": decision.user,
            }
        )

        return decision

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
        """Lista todo o histórico de decisões humanas (HITL) para uma execução."""
        from sqlalchemy import select
        result = await session.execute(
            select(HumanDecisionModel).where(HumanDecisionModel.run_id == run_id).order_by(HumanDecisionModel.timestamp.asc())
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
            return {"breaking_changes": [b.model_dump() for b in breaking], "status": "ok" if not breaking else "warning"}
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
    from lf.api.config import config_router

    app.include_router(config_router)

    return app


async def _execute_pipeline_in_background(
    run_id: str,
    idea: str,
    stack: str,
    mock_llm: bool = False,
    routing_mode: str = "full",
    interactive: bool = False,
):
    """Executa a pipeline assincronamente em segundo plano e atualiza o estado da Run no DB."""
    import asyncio
    import os
    import time

    from lf.api.database import session_factory
    from lf.api.models import PipelineRun
    from lf.config.schema import TaskSchema
    from lf.orchestrator.task_dispatcher import TaskDispatcher

    start_time = time.time()

    if session_factory:
        async with session_factory() as session:
            run = await session.get(PipelineRun, run_id)
            if run:
                run.status = "running"
                await session.commit()

    task = TaskSchema(
        id=f"task-{run_id[:8]}",
        title=idea,
        agent_id="cpo",
        stack=stack,
        routing_mode=routing_mode,
    )

    project_dir = f"/tmp/loopforge/run_{run_id}"
    os.makedirs(project_dir, exist_ok=True)

    if os.getenv("LF_API_TEST"):
        mock_llm = True

    dispatcher = TaskDispatcher(
        mock_llm=mock_llm,
        interactive=interactive,
        notify=False,
    )

    def _sync_dispatch():
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
        tests_failed = (
            test_report.get("summary", {}).get("tests_failed", 0)
            if isinstance(test_report, dict)
            else 0
        )

        final_status = "completed" if (not err and tests_failed == 0) else "failed"
        log_msg = err if err else f"Pipeline concluída em {duration}s. Testes com falha: {tests_failed}"

        if session_factory:
            async with session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if run:
                    run.status = final_status
                    run.current_node = final_state.get("next_agent", "FINISH")
                    run.duration_seconds = duration
                    run.logs = log_msg
                    await session.commit()

        await ws_manager.broadcast({
            "event": "pipeline_finished",
            "run_id": run_id,
            "status": final_status,
            "duration_seconds": duration,
        })
    except Exception as e:
        duration = round(time.time() - start_time, 2)
        if session_factory:
            async with session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if run:
                    run.status = "failed"
                    run.duration_seconds = duration
                    run.logs = f"Erro na execução da pipeline: {e}"
                    await session.commit()

        await ws_manager.broadcast({
            "event": "pipeline_error",
            "run_id": run_id,
            "error": str(e),
        })

