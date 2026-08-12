"""Testes da Memory API: CRUD de lições aprendidas em /api/v1/memory/lessons.

Cobre o contrato do MemoryPanel (ADE): listar com filtros de stack/query,
criar, atualizar e remover lições no telemetry.sqlite (MemoryManager).
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
    from lf.api.database import Base, engine, close_db, init_db

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
    """Client ASGI isolado: CWD no tmp_path (telemetry.sqlite da memória fica lá)."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _lesson(
    run_id: str = "run-1", stack: str = "python", idea: str = "API REST", text: str = "Li\u00e7\u00e3o de exemplo."
) -> dict:
    """Payload padrão de criação de lição."""
    return {"run_id": run_id, "stack": stack, "idea": idea, "lesson_text": text}


@pytest.mark.asyncio
async def test_memory_crud_flow(client: AsyncClient):
    """Fluxo completo: criar → listar → buscar → atualizar → remover."""
    # Cria duas lições em stacks distintas.
    r1 = await client.post("/api/v1/memory/lessons", json=_lesson())
    assert r1.status_code == 201
    lesson = r1.json()
    assert lesson["id"] == 1
    assert lesson["stack"] == "python"
    assert lesson["run_id"] == "run-1"
    assert lesson["lesson_text"] == "Li\u00e7\u00e3o de exemplo."

    r2 = await client.post("/api/v1/memory/lessons", json=_lesson(run_id="run-2", stack="java", idea="Padrões GoF"))
    assert r2.status_code == 201
    assert r2.json()["id"] == 2

    # Lista sem filtro retorna tudo.
    r = await client.get("/api/v1/memory/lessons")
    assert r.status_code == 200
    assert len(r.json()) == 2

    # Filtro por stack é case-insensitive.
    r = await client.get("/api/v1/memory/lessons", params={"stack": "PYTHON"})
    assert [x["id"] for x in r.json()] == [1]
    r = await client.get("/api/v1/memory/lessons", params={"stack": "java"})
    assert [x["id"] for x in r.json()] == [2]

    # Busca por palavras-chave reusa o ranqueamento por relevância.
    r = await client.get("/api/v1/memory/lessons", params={"query": "exemplo"})
    assert [x["id"] for x in r.json()] == [1]
    r = await client.get("/api/v1/memory/lessons", params={"query": "inexistente"})
    assert r.json() == []

    # PATCH parcial atualiza só o campo enviado.
    r = await client.patch("/api/v1/memory/lessons/1", json={"lesson_text": "Texto atualizado."})
    assert r.status_code == 200
    updated = r.json()
    assert updated["lesson_text"] == "Texto atualizado."
    assert updated["stack"] == "python"  # não foi tocado

    # DELETE remove e o GET passa a retornar vazio.
    r = await client.delete("/api/v1/memory/lessons/1")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    r = await client.get("/api/v1/memory/lessons")
    assert [x["id"] for x in r.json()] == [2]


@pytest.mark.asyncio
async def test_memory_list_default_limit_and_order(client: AsyncClient, monkeypatch):
    """Lista ordena por created_at DESC e respeita o limite padrão de 50."""
    clock = {"t": 1000.0}
    monkeypatch.setattr("lf.memory.manager.time.time", lambda: clock["t"])
    for i in range(3):
        clock["t"] += 1.0
        r = await client.post("/api/v1/memory/lessons", json=_lesson(run_id=f"run-{i}", idea=f"ideia-{i}"))
        assert r.status_code == 201

    # Mais recentes primeiro.
    r = await client.get("/api/v1/memory/lessons")
    assert [x["idea"] for x in r.json()] == ["ideia-2", "ideia-1", "ideia-0"]

    # limit param reduz o retorno.
    r = await client.get("/api/v1/memory/lessons", params={"limit": 2})
    assert len(r.json()) == 2
    # limit inválido → 422 (ge=1).
    r = await client.get("/api/v1/memory/lessons", params={"limit": 0})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_memory_errors(client: AsyncClient):
    """Erros do contrato: 404 em PATCH/DELETE de id inexistente e 422 em texto vazio."""
    r = await client.patch("/api/v1/memory/lessons/99", json={"idea": "nova"})
    assert r.status_code == 404

    r = await client.delete("/api/v1/memory/lessons/99")
    assert r.status_code == 404

    r = await client.post("/api/v1/memory/lessons", json=_lesson(text="   "))
    assert r.status_code == 422

    # POST sem campos obrigatórios → 422 do pydantic.
    r = await client.post("/api/v1/memory/lessons", json={"run_id": "run-x"})
    assert r.status_code == 422
