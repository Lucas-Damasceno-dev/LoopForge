"""Testes M-08/M-09/M-10 da Fase A: fonte única de budget, custo por run e
hard-stop de budget como PAUSA + override + resume.

Fluxo E2E: run com budget baixo (ade.yaml em tmp_path) estoura o CircuitBreaker
no nó developer → a run fica PAUSADA (checkpoint pendente em 'developer', NÃO
falha) → POST /cost/override com limite maior (aplica ao CircuitBreaker do
checkpoint) → resume re-executa o developer e conclui.
"""
import asyncio
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.config.loader import save_ade_config
from lf.config.schema import AdeBudget, AdeConfig, TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.llm_factory import CostTracker


def _app_with_costs():
    """create_app() + registro do router de custos (M-08/M-10).

    O router ``lf.api.costs.costs_router`` é registrado pelo orquestrador em
    app.py (outro lane); aqui registramos manualmente para o teste E2E.
    """
    app = create_app()
    from lf.api.costs import costs_router

    app.include_router(costs_router)
    return app


@pytest_asyncio.fixture(autouse=True)
async def setup_api(tmp_path, monkeypatch):
    """Banco API SQLite limpo em tmp_path (mesmo padrão de test_api.py)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


def _write_ade_budget(tmp_path: Path, max_usd: float) -> None:
    """ade.yaml com budget (fonte única M-08) no diretório de trabalho."""
    cfg_path = tmp_path / ".loopforge" / "ade.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    save_ade_config(AdeConfig(budget=AdeBudget(max_usd=max_usd)), cfg_path)


async def _next_nodes_of_thread(thread_id: str) -> list[str]:
    """Nós PENDENTES do checkpoint da thread (vazio = run terminou)."""
    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return list(snap.next) if snap else []
    finally:
        await saver.conn.close()


async def _wait_status(client: AsyncClient, run_id: str, timeout: float = 30.0) -> str:
    """Poll GET /api/runs/{id} até a run sair de pending/running."""
    waited = 0.0
    status = "pending"
    while waited < timeout:
        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        status = resp.json()["status"]
        if status in ("completed", "failed"):
            return status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em {timeout}s (status: {status})")


def test_budget_pause_dispatcher_and_resume_after_override(tmp_path, monkeypatch):
    """M-10 no nível do dispatcher: estouro de budget pausa (não falha),
    resume sem override permanece pausado, override + resume conclui."""
    monkeypatch.chdir(tmp_path)
    _write_ade_budget(tmp_path, 0.01)

    task = TaskSchema(id="task-1", title="Budget pause", agent_id="developer", stack="python", routing_mode="fast")
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)

    # 1. Dispatch com budget mínimo -> developer estoura -> PAUSA (não falha)
    result = dispatcher.dispatch(task, project_id="run-budget-pause-1")
    assert not result.get("error"), f"run deveria estar pausada, não falha: {result.get('error')}"
    thread_id = "run-budget-pause-1"
    assert "developer" in asyncio.run(_next_nodes_of_thread(thread_id)), "run deveria estar pausada no developer"

    # 2. Resume SEM override -> continua pausada (budget segue estourado)
    resumed = dispatcher.resume(thread_id=thread_id)
    assert not resumed.get("error")
    assert "developer" in asyncio.run(_next_nodes_of_thread(thread_id))

    # 3. Override (mesmo efeito do POST /cost/override): novo limite aplicado
    #    ao CircuitBreaker do checkpoint (trajectories.db)
    from lf.api.costs import _apply_override_to_checkpoint

    applied = asyncio.run(_apply_override_to_checkpoint("budget-pause-1", thread_id, 50.0))
    assert applied is True, "override deveria atualizar o CircuitBreaker do checkpoint"

    # 4. Resume com limite maior -> developer re-executa e a run conclui
    resumed2 = dispatcher.resume(thread_id=thread_id)
    assert not resumed2.get("error"), f"resume com override falhou: {resumed2.get('error')}"
    assert resumed2.get("next_agent") == "FINISH"
    assert asyncio.run(_next_nodes_of_thread(thread_id)) == []


@pytest.mark.asyncio
async def test_budget_hard_stop_pause_override_resume_e2e():
    """E2E via API: run pausada por budget, override e resume (M-08/M-10)."""
    _write_ade_budget(Path.cwd(), 0.01)
    app = _app_with_costs()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/runs",
            json={"idea": "Hard-stop budget", "stack": "python", "mock_llm": True},
        )
        assert resp.status_code == 201
        run_id = resp.json()["id"]
        thread_id = f"run-{run_id}"

        status = await _wait_status(client, run_id)
        assert status != "failed", f"run NÃO deveria falhar (hard-stop = pausa): {status}"

        # PAUSA: checkpoint pendente no nó developer
        assert "developer" in await _next_nodes_of_thread(thread_id), "run deveria estar pausada no developer"

        # GET /cost reflete o budget de ade.yaml (fonte única) antes do override
        cost = (await client.get(f"/api/v1/runs/{run_id}/cost")).json()
        assert cost["budget"]["max_usd"] == 0.01
        assert cost["budget_warning"] is False

        # Override com limite maior (aplica ao checkpoint)
        ov = await client.post(f"/api/v1/runs/{run_id}/cost/override", json={"max_usd": 50.0})
        assert ov.status_code == 200
        assert ov.json()["budget"]["max_usd"] == 50.0

        # Resume -> conclui
        resume = await client.post(f"/api/runs/{run_id}/resume")
        assert resume.status_code == 200
        waited = 0.0
        data: dict = {}
        while waited < 20.0:
            await asyncio.sleep(0.2)
            r = await client.get(f"/api/runs/{run_id}")
            data = r.json()
            if data.get("logs") and "retomada" in data["logs"]:
                break
            if data["status"] == "failed":
                break
            waited += 0.2
        assert data.get("status") != "failed", f"resume falhou: {data}"
        assert data.get("logs") and "retomada" in data["logs"], (
            f"resume não concluiu após override: {data}"
        )
        assert await _next_nodes_of_thread(thread_id) == []


def test_llm_costs_additive_migration_and_run_fields(tmp_path):
    """M-08/M-09: migração aditiva idempotente de llm_costs + track com run_id/node/estimated."""
    db = tmp_path / "telemetry.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE llm_costs (id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT NOT NULL, "
        "prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL, "
        "cost_usd REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()

    tracker = CostTracker(db)  # migra aditivamente (PRAGMA + ALTER)
    cols = {r[1] for r in sqlite3.connect(str(db)).execute("PRAGMA table_info(llm_costs)")}
    assert {"run_id", "node", "estimated"} <= cols, f"colunas ausentes: {cols}"

    tracker.track("default", "abcd", "xy", run_id="run-abc", node="developer", estimated=True)
    row = sqlite3.connect(str(db)).execute(
        "SELECT run_id, node, estimated FROM llm_costs WHERE run_id = 'run-abc'"
    ).fetchone()
    assert row == ("run-abc", "developer", 1)

    # Idempotente: reabrir não quebra nem duplica colunas
    CostTracker(db)
    cols2 = {r[1] for r in sqlite3.connect(str(db)).execute("PRAGMA table_info(llm_costs)")}
    assert cols2 == cols


def test_opencode_subprocess_tracks_estimated_cost(tmp_path, monkeypatch):
    """M-09: o path OpenCode subprocess registra custo ESTIMADO em llm_costs."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from lf.runner.opencode import llm as llm_module
    from lf.runner.opencode.models import OpenCodeResult

    fake = OpenCodeResult(exit_code=0, stdout="resposta do subprocesso", stderr="", changed_files=[])
    monkeypatch.setattr(llm_module.OpenCodeRunner, "run", lambda *a, **k: fake)

    out = llm_module.call_llm_via_opencode("sys", "user", cache=False, mock=False)
    assert out == "resposta do subprocesso"

    row = sqlite3.connect(".loopforge/telemetry.sqlite").execute(
        "SELECT estimated, cost_usd FROM llm_costs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "nenhum custo registrado para o subprocesso"
    assert row[0] == 1, "custo do subprocesso deveria ser estimado"
    assert row[1] > 0


@pytest.mark.asyncio
async def test_cost_endpoint_sums_warning_and_estimated(tmp_path, monkeypatch):
    """M-08: GET /cost soma o ledger do run e emite budget_warning aos 80%."""
    _write_ade_budget(tmp_path, 0.002)
    from lf.api.database import session_factory
    from lf.api.models import PipelineRun

    async with session_factory() as session:
        run = PipelineRun(idea="Cost", stack="python", status="completed")
        session.add(run)
        await session.commit()
        run_id = run.id

    tracker = CostTracker(Path(".loopforge/telemetry.sqlite"))
    # default: (0.001 input, 0.002 output)/1k → 1000 tokens input = 0.001 USD
    tracker.track("default", "", "", prompt_tokens=1000, completion_tokens=0, run_id=run_id, node="developer")
    tracker.track("default", "", "", prompt_tokens=1000, completion_tokens=0, run_id=run_id, node="qa", estimated=True)

    app = _app_with_costs()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/runs/{run_id}/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["spent_usd"] == pytest.approx(0.002, abs=1e-6)
        assert data["estimated"] is True
        assert data["budget"]["max_usd"] == 0.002
        assert data["budget"]["percent_used"] == pytest.approx(1.0, abs=1e-3)
        assert data["budget_warning"] is True

        # 404 para run inexistente (GET e POST)
        assert (await client.get("/api/v1/runs/nao-existe/cost")).status_code == 404
        assert (await client.post("/api/v1/runs/nao-existe/cost/override", json={"max_usd": 5})).status_code == 404

        # Override body vazio → usa ade.yaml (fonte única)
        ov = await client.post(f"/api/v1/runs/{run_id}/cost/override")
        assert ov.status_code == 200
        assert ov.json()["budget"]["max_usd"] == 0.002

        # Override inválido → 422 (max_usd <= 0)
        bad = await client.post(f"/api/v1/runs/{run_id}/cost/override", json={"max_usd": 0})
        assert bad.status_code == 422
