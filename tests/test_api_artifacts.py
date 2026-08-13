"""Testes do endpoint de artifacts (GET /api/v1/runs/{id}/artifacts)."""

import asyncio
import contextlib
import os
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from lf.api.app import create_app

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)

RUN_ID = "11111111-2222-3333-4444-555555555555"


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_api_timeline.py)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)
    from lf.api.database import init_db

    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    from lf.api.database import close_db

    await close_db()
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


async def _insert_run(run_id: str, thread_id: str | None = None) -> None:
    """Insere uma run direto na tabela pipeline_runs (sem pipeline)."""
    from lf.api.database import engine
    from lf.api.models import PipelineRun

    async with engine.begin() as conn:
        await conn.execute(
            insert(PipelineRun).values(
                id=run_id, idea="teste artifacts", stack="python", status="completed", thread_id=thread_id
            )
        )


@pytest.mark.asyncio
async def test_artifacts_404_run_inexistente():
    # SEM chdir: a URL do engine API é CWD-relative no connect-time e o
    # conftest.py já seta LF_API_TEST=1 para a sessão toda — a fixture local
    # init_db criou o test_api.sqlite na raiz; chdir quebraria o insert.
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/runs/{RUN_ID}/artifacts")
        assert r.status_code == 404
        assert r.json()["detail"] == "Run not found"


@pytest.mark.asyncio
async def test_artifacts_200_vazio_sem_checkpoint():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _insert_run(RUN_ID)
        r = await ac.get(f"/api/v1/runs/{RUN_ID}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == RUN_ID
        assert data["node_artifacts"] == {}
        assert data["tokens"] == []
        assert data["degraded"] is False
        assert data["degraded_reason"] is None
        assert data["circuit_breaker"] is None
        assert data["lessons"] == []


@pytest.mark.asyncio
async def test_artifacts_checkpoint_corrompido_graceful(tmp_path, monkeypatch):
    """Checkpoint com circuit_breaker corrompido → 200 com artifacts vazios e degraded False."""
    monkeypatch.setattr("lf.api.artifacts._trajectories_db", lambda: tmp_path / "trajectories.db")
    monkeypatch.setattr("lf.api.artifacts._telemetry_db", lambda: tmp_path / "telemetry.sqlite")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _insert_run(RUN_ID)
        await _seed_thread(
            tmp_path / "trajectories.db",
            f"run-{RUN_ID}",
            "seed-corrupt",
            {
                "epic": {"title": "Login"},
                "degraded": True,
                "degraded_reason": "fallback",
                # consecutive_failures=None viola o schema → ValidationError →
                # cai no except graceful (200, artifacts vazios, degraded False).
                "circuit_breaker": {"consecutive_failures": None},
            },
        )
        r = await ac.get(f"/api/v1/runs/{RUN_ID}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["node_artifacts"] == {}
        assert data["degraded"] is False
        assert data["degraded_reason"] is None
        assert data["circuit_breaker"] is None


@pytest.mark.asyncio
async def test_artifacts_thread_id_persistido(tmp_path, monkeypatch):
    """Run com thread_id custom → artifacts vêm da thread persistida (ADR-0003)."""
    monkeypatch.setattr("lf.api.artifacts._trajectories_db", lambda: tmp_path / "trajectories.db")
    monkeypatch.setattr("lf.api.artifacts._telemetry_db", lambda: tmp_path / "telemetry.sqlite")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _insert_run(RUN_ID, thread_id="custom-thread")
        await _seed_thread(
            tmp_path / "trajectories.db",
            "custom-thread",
            "seed-thread",
            {"epic": {"title": "Custom Thread"}},
        )
        r = await ac.get(f"/api/v1/runs/{RUN_ID}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["node_artifacts"]["cpo"]["output"]["epic"] == {"title": "Custom Thread"}


async def _seed_thread(db_path: Path, thread_id: str, checkpoint_id: str, channels: dict) -> None:
    """Grava um checkpoint direto no checkpointer em db_path (padrão test_api_trajectories)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(db_path)
    try:
        await saver.setup()
        await saver.aput(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
            {"id": checkpoint_id, "v": 1, "ts": "2026-08-05T00:00:00Z", "channel_values": channels},
            {"source": "loop", "step": 0},
            {},
        )
    finally:
        await saver.conn.close()


def _seed_telemetry(db_path: Path, run_id: str) -> None:
    """Cria llm_costs + lessons em telemetry.sqlite (db_path) com dados da run."""
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS llm_costs (id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT, "
            "prompt_tokens INTEGER, completion_tokens INTEGER, cost_usd REAL, created_at REAL, "
            "run_id TEXT, node TEXT, estimated INTEGER DEFAULT 0)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS lessons (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, "
            "stack TEXT NOT NULL, idea TEXT NOT NULL, lesson_text TEXT NOT NULL, created_at REAL NOT NULL)"
        )
        conn.execute(
            "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd, "
            "created_at, run_id, node, estimated) "
            "VALUES ('oc/test', 100, 50, 0.01, 1.0, ?, 'developer', 0)",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd, "
            "created_at, run_id, node, estimated) "
            "VALUES ('oc/test', 20, 10, 0.002, 2.0, ?, 'qa', 1)",
            (run_id,),
        )
        conn.execute(
            "INSERT INTO lessons (run_id, stack, idea, lesson_text, created_at) "
            "VALUES (?, 'python', 'teste', 'lição de teste', 3.0)",
            (run_id,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_artifacts_mapeia_canais_por_no(tmp_path, monkeypatch):
    # Isolamento SEM chdir (engine API é CWD-relative no connect-time):
    # monkeypatch das helpers de path do módulo aponta para tmp_path.
    monkeypatch.setattr("lf.api.artifacts._trajectories_db", lambda: tmp_path / "trajectories.db")
    monkeypatch.setattr("lf.api.artifacts._telemetry_db", lambda: tmp_path / "telemetry.sqlite")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await _insert_run(RUN_ID)
        await _seed_thread(
            tmp_path / "trajectories.db",
            f"run-{RUN_ID}",
            "seed-1",
            {
                "epic": {"title": "Login"},
                "tech_spec": "FastAPI + JWT",
                "code": "def main():\n    pass\n",
                "test_report": {"summary": {"tests_passed": 1, "tests_failed": 0, "total_tests": 1}},
                "security_review": {"vulnerabilities_found": []},
                "devops_manifest": {
                    "deployability_score": 90,
                    "status": "ok",
                    "dockerfile_created": True,
                    "ci_workflow_created": True,
                    "recommendations": [],
                },
                "security_report": "## Security (md)",
                "devops_report": "## DevOps (md)",
                "degraded": True,
                "degraded_reason": "mock fallback",
                "circuit_breaker": {
                    "state": "closed",
                    "consecutive_failures": 1,
                    "total_iterations": 3,
                    "total_cost": 0.5,
                    "max_consecutive_failures": 5,
                    "max_iterations": 20,
                    "max_total_cost": 10.0,
                    "cost_per_iteration": 0.05,
                    "reset_timeout": 300,
                    "last_failure_time": None,
                },
            },
        )
        _seed_telemetry(tmp_path / "telemetry.sqlite", RUN_ID)

        r = await ac.get(f"/api/v1/runs/{RUN_ID}/artifacts")
        assert r.status_code == 200
        data = r.json()

        # Mapeamento por nó
        assert data["node_artifacts"]["cpo"]["output"]["epic"] == {"title": "Login"}
        assert data["node_artifacts"]["tech_lead"]["output"]["tech_spec"] == "FastAPI + JWT"
        assert data["node_artifacts"]["developer"]["output"]["code"].startswith("def main")
        assert data["node_artifacts"]["qa"]["output"]["test_report"]["summary"]["tests_passed"] == 1
        pa = data["node_artifacts"]["parallel_audit"]["output"]
        assert pa["security_review"]["vulnerabilities_found"] == []
        assert pa["devops_manifest"]["deployability_score"] == 90
        # markdown renomeado com sufixo _md
        assert pa["security_report_md"] == "## Security (md)"
        assert pa["devops_report_md"] == "## DevOps (md)"
        assert "security_report" not in pa

        # Tokens agrupados por nó
        tokens = {t["node"]: t for t in data["tokens"]}
        assert tokens["developer"]["prompt_tokens"] == 100
        assert tokens["developer"]["completion_tokens"] == 50
        assert tokens["developer"]["cost_usd"] == 0.01
        assert tokens["qa"]["estimated"] is True

        # Estado da run
        assert data["degraded"] is True
        assert data["degraded_reason"] == "mock fallback"
        assert data["circuit_breaker"]["state"] == "closed"
        assert data["circuit_breaker"]["consecutive_failures"] == 1
        assert len(data["lessons"]) == 1
        assert data["lessons"][0]["lesson_text"] == "lição de teste"


async def _run_mock_pipeline(client: AsyncClient, idea: str = "Artifacts") -> tuple[str, str]:
    """Cria e espera uma pipeline mock terminar; devolve (run_id, status)."""
    resp = await client.post("/api/runs", json={"idea": idea, "stack": "python", "mock_llm": True})
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    waited = 0.0
    while waited < 30.0:
        status = (await client.get(f"/api/runs/{run_id}")).json()["status"]
        if status in ("completed", "failed", "paused"):
            return run_id, status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em 30s")


@pytest.mark.asyncio
async def test_artifacts_e2e_pipeline_mock():
    """Pipeline mock completa → artifacts com nós do fluxo full + tokens.

    SEM chdir: a URL do engine API é CWD-relative no connect-time e a fixture
    local LF_API_TEST=1 criou o test_api.sqlite na raiz (padrão timeline) — a
    pipeline escreve checkpoints no .loopforge/trajectories.db real (gitignored)
    e o endpoint lê do mesmo CWD-relative, então os caminhos coincidem.
    """
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        run_id, status = await _run_mock_pipeline(ac, idea="Artifacts e2e")
        assert status == "completed"

        r = await ac.get(f"/api/v1/runs/{run_id}/artifacts")
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == run_id
        # Fluxo full: cpo→…→parallel_audit escreve artifact em cada nó
        assert "cpo" in data["node_artifacts"]
        assert "developer" in data["node_artifacts"]
        assert "parallel_audit" in data["node_artifacts"]
        assert "circuit_breaker" in data and data["circuit_breaker"] is not None
        # mock devolve resposta normal (sem exceção), então os nós NÃO marcam
        # degraded=True (só no fallback por erro) — assert fixo em False (o
        # in (True, False) anterior era vácuo: degraded já é bool).
        assert data["degraded"] is False
