"""Testes da Agents API: CRUD de agentes em /api/v1/agents.

Cobre o contrato do S2 (CRUD de agentes): listar (ordenado por name),
criar (uuid, name único), buscar, atualizar (PATCH-style no PUT) e remover.
Padrão de fixture/DB do test_memory_api.py.
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


def _agent(name: str = "dev", **overrides) -> dict:
    """Payload padrão de criação de agente."""
    payload = {"name": name, "prompt": "rode o pipeline"}
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_agents_crud_flow(client: AsyncClient):
    """Fluxo completo: criar → buscar → listar → atualizar → remover."""
    r = await client.post("/api/v1/agents", json=_agent())
    assert r.status_code == 201
    agent = r.json()
    assert agent["name"] == "dev"
    assert agent["prompt"] == "rode o pipeline"
    assert agent["id"]
    assert agent["created_at"] and agent["updated_at"]
    assert agent["temperature"] == 0.7  # default propagado
    assert agent["permissions"] == []

    agent_id = agent["id"]

    # GET individual
    r = await client.get(f"/api/v1/agents/{agent_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "dev"

    # Cria segundo agente com temperature custom para validar ordenação por name.
    r = await client.post("/api/v1/agents", json=_agent(name="zeta", temperature=1.2))
    assert r.status_code == 201

    # Lista ordenada por name
    r = await client.get("/api/v1/agents")
    assert r.status_code == 200
    assert [x["name"] for x in r.json()] == ["dev", "zeta"]

    # PUT parcial: só temperature muda, demais campos mantêm
    r = await client.put(f"/api/v1/agents/{agent_id}", json={"temperature": 1.9})
    assert r.status_code == 200
    updated = r.json()
    assert updated["temperature"] == 1.9
    assert updated["name"] == "dev"
    assert updated["prompt"] == "rode o pipeline"
    assert updated["permissions"] == []

    # DELETE remove e GET passa a 404
    r = await client.delete(f"/api/v1/agents/{agent_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    r = await client.get(f"/api/v1/agents/{agent_id}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_agents_list_empty(client: AsyncClient):
    """Lista vazia retorna [], não 404."""
    r = await client.get("/api/v1/agents")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_agents_404_paths(client: AsyncClient):
    """404 em GET/PUT/DELETE de id inexistente."""
    r = await client.get("/api/v1/agents/nao-existe")
    assert r.status_code == 404
    assert r.json()["detail"] == "Agent not found"

    r = await client.put("/api/v1/agents/nao-existe", json={"temperature": 1.0})
    assert r.status_code == 404

    r = await client.delete("/api/v1/agents/nao-existe")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_agents_name_duplicado_422(client: AsyncClient):
    """POST com name duplicado → 422 'name already exists'."""
    r = await client.post("/api/v1/agents", json=_agent(name="dev"))
    assert r.status_code == 201

    r = await client.post("/api/v1/agents", json=_agent(name="dev"))
    assert r.status_code == 422
    assert r.json()["detail"] == "name already exists"


@pytest.mark.asyncio
async def test_agents_put_name_duplicado_422(client: AsyncClient):
    """PUT trocando name para um existente → 422 'name already exists'."""
    r = await client.post("/api/v1/agents", json=_agent(name="dev"))
    assert r.status_code == 201
    r = await client.post("/api/v1/agents", json=_agent(name="zeta"))
    assert r.status_code == 201

    zeta_id = r.json()["id"]
    r = await client.put(f"/api/v1/agents/{zeta_id}", json={"name": "dev"})
    assert r.status_code == 422
    assert r.json()["detail"] == "name already exists"


@pytest.mark.asyncio
async def test_agents_put_campos_none_mantem_valor(client: AsyncClient):
    """PUT com body contendo campos None explícitos mantém valores (PATCH-style)."""
    r = await client.post(
        "/api/v1/agents",
        json=_agent(name="dev", temperature=1.5, permissions=["run"]),
    )
    assert r.status_code == 201
    agent_id = r.json()["id"]

    r = await client.put(
        f"/api/v1/agents/{agent_id}",
        json={"temperature": None, "permissions": None},
    )
    assert r.status_code == 200
    updated = r.json()
    assert updated["temperature"] == 1.5
    assert updated["permissions"] == ["run"]
    assert updated["name"] == "dev"
