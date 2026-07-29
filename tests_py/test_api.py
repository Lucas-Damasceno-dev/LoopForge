"""Testes da API REST, WebSockets e Auth do LoopForge v6 (Módulo Core lf.api)."""

import os

import pytest
from click.testing import CliRunner
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.cli.commands.serve import serve_cmd


@pytest.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite em memória para cada teste."""
    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    await init_db()
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)




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
async def test_dashboard_ui(client: AsyncClient):
    """GET / e /dashboard devem retornar HTMLResponse."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "LoopForge v6" in resp.text


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


@pytest.mark.asyncio
async def test_update_and_delete_run(client: AsyncClient):
    """PATCH /api/runs/{id} e DELETE /api/runs/{id}."""
    create_resp = await client.post("/api/runs", json={"idea": "Update me"})
    run_id = create_resp.json()["id"]

    resp_patch = await client.patch(
        f"/api/runs/{run_id}",
        json={"status": "running", "current_node": "developer"},
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "running"

    resp_del = await client.delete(f"/api/runs/{run_id}")
    assert resp_del.status_code == 204


def test_cli_serve_cmd():
    """Verifica que o comando 'lf serve --help' roda perfeitamente."""
    runner = CliRunner()
    res = runner.invoke(serve_cmd, ["--help"])
    assert res.exit_code == 0
    assert "Inicia o servidor de API REST" in res.output