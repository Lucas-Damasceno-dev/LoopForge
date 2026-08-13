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
    """Run enfileirada (slot ocupado) aparece na fila com status 'queued'."""
    app = create_app()
    # max_concurrent=1 → 1ª run ocupa o slot ativo, 2ª fica enfileirada
    # (a pipeline mock da 1ª não termina na janela entre os dois POSTs).
    app.state.run_queue.max_concurrent = 1
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.post("/api/runs", json={"idea": "Fila Q1", "stack": "python", "mock_llm": True})
        assert r1.status_code == 201
        r2 = await ac.post("/api/runs", json={"idea": "Fila Q2", "stack": "python", "mock_llm": True})
        assert r2.status_code == 201
        queued_run_id = r2.json()["id"]

        r = await ac.get("/api/v1/runs/queue")
        assert r.status_code == 200
        data = r.json()
        assert data["max_concurrent"] >= 1
        assert data["active_count"] >= 1
        assert r1.json()["id"] in data["active"]

        matches = [q for q in data["queued"] if q["id"] == queued_run_id]
        assert matches, f"run {queued_run_id} não está na fila: {data}"
        assert matches[0]["idea"] == "Fila Q2"
        assert matches[0]["stack"] == "python"
        assert matches[0]["status"] == "queued"
        assert matches[0]["created_at"] is not None


@pytest.mark.asyncio
async def test_queue_vazia():
    """Sem runs pendentes, a fila retorna lista vazia com contadores válidos."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/runs/queue")
        assert r.status_code == 200
        data = r.json()
        assert data["max_concurrent"] >= 1
        assert data["queued"] == []
