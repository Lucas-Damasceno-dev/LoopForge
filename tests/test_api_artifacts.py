"""Testes do endpoint de artifacts (GET /api/v1/runs/{id}/artifacts)."""

import contextlib
import os

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


async def _insert_run(run_id: str) -> None:
    """Insere uma run direto na tabela pipeline_runs (sem pipeline)."""
    from lf.api.database import engine
    from lf.api.models import PipelineRun

    async with engine.begin() as conn:
        await conn.execute(
            insert(PipelineRun).values(id=run_id, idea="teste artifacts", stack="python", status="completed")
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
