"""Snapshot no create-run (S3): override via RunCreate.snapshot.

Cobre: POST /runs com snapshot válido persiste no run; snapshot inválido
(ciclo) → 422; sem snapshot + pipeline_id → deriva do template (regressão);
RunResponse expõe snapshot.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

PIPELINE_BODY = {
    "name": "snap-pipeline",
    "description": "template",
    "nodes": [
        {"id": "n1", "type": "input", "agent_id": None, "config": {}},
        {"id": "n2", "type": "agent", "agent_id": "developer", "config": {}},
        {"id": "n3", "type": "output", "agent_id": None, "config": {}},
    ],
    "edges": [
        {"source": "n1", "target": "n2", "type": "sequential", "condition": None, "max_retries": 0},
        {"source": "n2", "target": "n3", "type": "sequential", "condition": None, "max_retries": 0},
    ],
}


@pytest_asyncio.fixture(autouse=True)
async def setup_snapshot_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


async def _create_pipeline(app, body: dict) -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/api/v1/pipelines", json=body)
        assert r.status_code == 201, r.text
        return r.json()["id"]


@pytest.mark.asyncio
async def test_snapshot_override_persiste_no_run():
    app = create_app()
    pid = await _create_pipeline(app, PIPELINE_BODY)
    override = {**PIPELINE_BODY, "description": "editada pelo usuário"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={
                "idea": "com snapshot",
                "stack": "python",
                "mock_llm": True,
                "pipeline_id": pid,
                "snapshot": override,
            },
        )
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["snapshot"]["description"] == "editada pelo usuário"
        assert run["pipeline_id"] == pid
        # GET do run devolve o snapshot persistido
        r2 = await ac.get(f"/api/v1/runs/{run['id']}")
        assert r2.status_code == 200
        assert r2.json()["snapshot"]["description"] == "editada pelo usuário"


@pytest.mark.asyncio
async def test_snapshot_sem_pipeline_id():
    """Snapshot próprio sem template vinculado — run nasce com snapshot."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "só snapshot", "stack": "python", "mock_llm": True, "snapshot": PIPELINE_BODY},
        )
        assert r.status_code == 201, r.text
        assert r.json()["snapshot"]["name"] == "snap-pipeline"


@pytest.mark.asyncio
async def test_snapshot_invalido_422():
    """Snapshot com ciclo → 422 (validação reutilizada do template)."""
    app = create_app()
    ciclico = {
        **PIPELINE_BODY,
        "edges": [
            {"source": "n1", "target": "n2", "type": "sequential", "condition": None, "max_retries": 0},
            {"source": "n2", "target": "n1", "type": "sequential", "condition": None, "max_retries": 0},
        ],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "ciclo", "stack": "python", "mock_llm": True, "snapshot": ciclico},
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_sem_snapshot_deriva_template_regressao():
    """Regressão: sem snapshot + pipeline_id → snapshot do template."""
    app = create_app()
    pid = await _create_pipeline(app, PIPELINE_BODY)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/runs",
            json={"idea": "sem override", "stack": "python", "mock_llm": True, "pipeline_id": pid},
        )
        assert r.status_code == 201, r.text
        assert r.json()["snapshot"]["description"] == "template"
