"""Testes da fila E3 (GET /api/v1/runs/queue — M-21).

Cobre o endpoint que expõe o estado da fila: runs ativas (até max_concurrent)
+ runs `queued` aguardando vaga, com idea/status/created_at vindos da tabela
pipeline_runs.
"""

import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


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


@pytest.mark.asyncio
async def test_queue_retorna_run_queued():
    """Fila determinística (sem pipeline): run queued aparece com metadados da DB.

    A fila E3 é populada manualmente (pending/params + run na pipeline_runs) em
    vez de POSTs reais — sem dependência de timing de pipeline mock (flaky). O
    GET devolve o shape exato: max_concurrent, active_count, active, queued.
    """
    from sqlalchemy import insert

    from lf.api.database import engine
    from lf.api.models import PipelineRun

    active_id = "aaaaaaaa-1111-2222-3333-444444444444"
    queued_id = "bbbbbbbb-1111-2222-3333-444444444444"
    async with engine.begin() as conn:
        await conn.execute(insert(PipelineRun).values(id=active_id, idea="Ativa", stack="python", status="running"))
        await conn.execute(insert(PipelineRun).values(id=queued_id, idea="Fila Q2", stack="python", status="queued"))

    app = create_app()
    app.state.run_queue.max_concurrent = 1
    q = app.state.run_queue
    q.active.add(active_id)
    q.pending.append(queued_id)
    q.params[queued_id] = {
        "idea": "Fila Q2",
        "stack": "python",
        "mock_llm": True,
        "routing_mode": "full",
        "interactive": False,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/runs/queue")
        assert r.status_code == 200
        data = r.json()
        assert data["max_concurrent"] == 1
        assert data["active_count"] == 1
        assert data["active"] == [active_id]
        assert len(data["queued"]) == 1
        item = data["queued"][0]
        assert item["id"] == queued_id
        assert item["idea"] == "Fila Q2"
        assert item["stack"] == "python"
        assert item["status"] == "queued"
        assert item["created_at"] is not None


@pytest.mark.asyncio
async def test_queue_vazia():
    """Sem runs pendentes, a fila retorna lista vazia com contadores válidos."""
    app = create_app()
    app.state.run_queue.max_concurrent = 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/runs/queue")
        assert r.status_code == 200
        data = r.json()
        assert data["max_concurrent"] == 1
        assert data["active_count"] == 0
        assert data["active"] == []
        assert data["queued"] == []


@pytest.mark.asyncio
async def test_queue_post_run_smoke():
    """Smoke: run criada via POST /api/runs aparece em active OU queued."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/runs", json={"idea": "Fila smoke", "stack": "python", "mock_llm": True})
        assert r.status_code == 201
        run_id = r.json()["id"]

        qr = await ac.get("/api/v1/runs/queue")
        assert qr.status_code == 200
        data = qr.json()
        assert data["max_concurrent"] >= 1
        all_ids = [q["id"] for q in data["queued"]] + data["active"]
        assert run_id in all_ids
