"""Testes da Pipelines API: CRUD de pipelines em /api/v1/pipelines.

Cobre o contrato do S3 (editor de pipelines): listar (ordenado por name),
criar (uuid, name único), buscar, atualizar (PATCH-style no PUT) e remover.
Inclui teste de auth (carry-over do S2): /api/v1/pipelines exige auth quando
LF_API_REQUIRE_AUTH=true (401 sem X-API-Key). Padrão de fixture/DB do
test_memory_api.py / test_agents_api.py.
"""

import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite de teste limpo para cada teste (padrão test_api.py)."""
    from lf.api.database import Base, close_db, engine, init_db

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in (
        ".loopforge/test_api.sqlite",
        ".loopforge/test_api.sqlite-wal",
        ".loopforge/test_api.sqlite-shm",
    ):
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest_asyncio.fixture
async def client(tmp_path, monkeypatch):
    """Client ASGI isolado: CWD no tmp_path (telemetry.sqlite fica lá)."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _pipeline(name: str = "flow", **overrides) -> dict:
    """Payload padrão de criação de pipeline (nó input + agente + aresta)."""
    payload = {
        "name": name,
        "description": "pipeline de teste",
        "nodes": [
            {"id": "n1", "type": "input"},
            {"id": "n2", "type": "agent", "agent_id": "agente-1"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_pipelines_crud_flow(client: AsyncClient):
    """Fluxo completo: criar → buscar → listar → atualizar → remover."""
    r = await client.post("/api/v1/pipelines", json=_pipeline())
    assert r.status_code == 201
    pl = r.json()
    assert pl["name"] == "flow"
    assert pl["description"] == "pipeline de teste"
    assert pl["id"]
    assert pl["created_at"] and pl["updated_at"]
    # nodes/edges roundtrip via coluna JSON
    assert [n["type"] for n in pl["nodes"]] == ["input", "agent"]
    assert pl["nodes"][1]["agent_id"] == "agente-1"
    assert pl["edges"] == [{"source": "n1", "target": "n2", "type": "sequential", "condition": None, "max_retries": 2}]

    pipeline_id = pl["id"]

    # GET individual
    r = await client.get(f"/api/v1/pipelines/{pipeline_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "flow"

    # Cria segundo pipeline para validar ordenação por name.
    r = await client.post("/api/v1/pipelines", json=_pipeline(name="zeta"))
    assert r.status_code == 201

    # Lista ordenada por name
    r = await client.get("/api/v1/pipelines")
    assert r.status_code == 200
    assert [x["name"] for x in r.json()] == ["flow", "zeta"]

    # PUT parcial: só description muda, nodes/edges mantêm
    r = await client.put(f"/api/v1/pipelines/{pipeline_id}", json={"description": "novo texto"})
    assert r.status_code == 200
    updated = r.json()
    assert updated["description"] == "novo texto"
    assert updated["name"] == "flow"
    assert [n["id"] for n in updated["nodes"]] == ["n1", "n2"]

    # DELETE remove e GET passa a 404
    r = await client.delete(f"/api/v1/pipelines/{pipeline_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    r = await client.get(f"/api/v1/pipelines/{pipeline_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pipelines_list_empty(client: AsyncClient):
    """Lista vazia retorna [], não 404."""
    r = await client.get("/api/v1/pipelines")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_pipelines_404_paths(client: AsyncClient):
    """404 em GET/PUT/DELETE de id inexistente."""
    r = await client.get("/api/v1/pipelines/nao-existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "Pipeline not found"

    r = await client.put("/api/v1/pipelines/nao-existe", json={"description": "x"})
    assert r.status_code == 404

    r = await client.delete("/api/v1/pipelines/nao-existe")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pipelines_name_duplicado_422(client: AsyncClient):
    """POST com name duplicado → 422 'name already exists'."""
    r = await client.post("/api/v1/pipelines", json=_pipeline(name="dev"))
    assert r.status_code == 201

    r = await client.post("/api/v1/pipelines", json=_pipeline(name="dev"))
    assert r.status_code == 422
    assert r.json()["detail"] == "name already exists"


@pytest.mark.asyncio
async def test_pipelines_put_name_duplicado_422(client: AsyncClient):
    """PUT trocando name para um existente → 422 'name already exists'."""
    r = await client.post("/api/v1/pipelines", json=_pipeline(name="dev"))
    assert r.status_code == 201
    r = await client.post("/api/v1/pipelines", json=_pipeline(name="zeta"))
    assert r.status_code == 201

    zeta_id = r.json()["id"]
    r = await client.put(f"/api/v1/pipelines/{zeta_id}", json={"name": "dev"})
    assert r.status_code == 422
    assert r.json()["detail"] == "name already exists"


@pytest.mark.asyncio
async def test_pipelines_put_campos_none_mantem_valor(client: AsyncClient):
    """PUT com body contendo campos None explícitos mantém valores (PATCH-style)."""
    r = await client.post(
        "/api/v1/pipelines",
        json=_pipeline(name="dev", description="original"),
    )
    assert r.status_code == 201
    pipeline_id = r.json()["id"]

    r = await client.put(
        f"/api/v1/pipelines/{pipeline_id}",
        json={"description": None, "nodes": None, "edges": None},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["description"] == "original"
    assert [n["id"] for n in updated["nodes"]] == ["n1", "n2"]
    assert updated["name"] == "dev"


@pytest.mark.asyncio
async def test_pipelines_requer_auth(tmp_path, monkeypatch):
    """Auth (carry-over S2): LF_API_REQUIRE_AUTH=true → 401 sem X-API-Key, 200 com key."""
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", "env-admin-key-123")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/pipelines")
        assert r.status_code == 401

        r = await ac.get("/api/v1/pipelines", headers={"X-API-Key": "env-admin-key-123"})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_pipelines_export_import_sync(client: AsyncClient, tmp_path):
    """Testa exportação para YAML, importação e sincronização de arquivos em disco."""
    # 1. Cria pipeline
    r = await client.post("/api/v1/pipelines", json=_pipeline(name="export_test"))
    assert r.status_code == 201
    pipeline_id = r.json()["id"]

    # 2. Exporta em YAML
    r = await client.get(f"/api/v1/pipelines/{pipeline_id}/export?format=yaml")
    assert r.status_code == 200
    assert "name: export_test" in r.text

    # 3. Exporta em JSON
    r = await client.get(f"/api/v1/pipelines/{pipeline_id}/export?format=json")
    assert r.status_code == 200
    assert r.json()["name"] == "export_test"

    # 4. Importa novo pipeline via JSON
    imported_payload = {
        "name": "imported_pipeline",
        "description": "via api",
        "nodes": [{"id": "n1", "type": "input"}],
        "edges": [],
    }
    r = await client.post("/api/v1/pipelines/import", json=imported_payload)
    assert r.status_code == 200
    assert r.json()["name"] == "imported_pipeline"

    # 5. Testa sync do diretório .loopforge/pipelines
    r = await client.post("/api/v1/pipelines/sync")
    assert r.status_code == 200
    assert "synced" in r.json()

