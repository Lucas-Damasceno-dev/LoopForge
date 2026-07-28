"""Testes da API REST do LoopForge.

Usa SQLite em memória via aiosqlite para evitar dependência de PostgreSQL.
"""

import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from lf.contrib.api.app import create_app
from lf.contrib.api.database import init_db, close_db, Base, engine, session_factory


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite em memória para cada teste."""
    os.environ["LF_API_TEST"] = "1"
    await init_db()
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)


@pytest.fixture
async def client():
    """Cliente HTTP async para testar a FastAPI app."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """GET /health deve retornar status ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "6.0.0"


@pytest.mark.asyncio
async def test_create_run(client: AsyncClient):
    """POST /api/runs deve criar uma nova run."""
    resp = await client.post("/api/runs", json={"idea": "Build a login page"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["idea"] == "Build a login page"
    assert data["status"] == "pending"
    assert data["stack"] == "python"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_run_with_custom_stack(client: AsyncClient):
    """POST /api/runs com stack personalizada."""
    resp = await client.post("/api/runs", json={"idea": "API service", "stack": "javascript"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["stack"] == "javascript"


@pytest.mark.asyncio
async def test_create_run_empty_idea_fails(client: AsyncClient):
    """POST /api/runs com ideia vazia deve falhar."""
    resp = await client.post("/api/runs", json={"idea": ""})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_runs_empty(client: AsyncClient):
    """GET /api/runs sem runs deve retornar lista vazia."""
    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_runs_with_data(client: AsyncClient):
    """GET /api/runs deve listar runs criadas."""
    await client.post("/api/runs", json={"idea": "Run 1"})
    await client.post("/api/runs", json={"idea": "Run 2"})

    resp = await client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_run_by_id(client: AsyncClient):
    """GET /api/runs/{id} deve retornar run específica."""
    create_resp = await client.post("/api/runs", json={"idea": "Specific run"})
    run_id = create_resp.json()["id"]

    resp = await client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_id
    assert resp.json()["idea"] == "Specific run"


@pytest.mark.asyncio
async def test_get_run_not_found(client: AsyncClient):
    """GET /api/runs/{id} com ID inexistente deve retornar 404."""
    resp = await client.get("/api/runs/non-existent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_run(client: AsyncClient):
    """PATCH /api/runs/{id} deve atualizar campos."""
    create_resp = await client.post("/api/runs", json={"idea": "Update me"})
    run_id = create_resp.json()["id"]

    resp = await client.patch(
        f"/api/runs/{run_id}",
        json={"status": "running", "current_agent": "developer"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["current_agent"] == "developer"


@pytest.mark.asyncio
async def test_update_run_not_found(client: AsyncClient):
    """PATCH /api/runs/{id} com ID inexistente deve retornar 404."""
    resp = await client.patch(
        "/api/runs/non-existent-id",
        json={"status": "running"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_run(client: AsyncClient):
    """DELETE /api/runs/{id} deve remover a run."""
    create_resp = await client.post("/api/runs", json={"idea": "Delete me"})
    run_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/runs/{run_id}")
    assert resp.status_code == 204

    # Verifica que foi removida
    get_resp = await client.get(f"/api/runs/{run_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_run_not_found(client: AsyncClient):
    """DELETE /api/runs/{id} com ID inexistente deve retornar 404."""
    resp = await client.delete("/api/runs/non-existent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_runs_pagination(client: AsyncClient):
    """GET /api/runs deve suportar paginação via skip/limit."""
    for i in range(5):
        await client.post("/api/runs", json={"idea": f"Run {i}"})

    resp = await client.get("/api/runs?skip=0&limit=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5

    resp = await client.get("/api/runs?skip=2&limit=2")
    assert len(resp.json()["items"]) == 2