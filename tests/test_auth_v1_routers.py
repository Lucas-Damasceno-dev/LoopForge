"""Testes de auth (M-03) nas rotas v1 de Trajectories, MCP, Providers e Config.

Sem X-API-Key (com auth ativada) → 401; com a key correta → 200.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

KEY = "teste-key-123"


@pytest_asyncio.fixture(autouse=True)
async def setup_auth_env(tmp_path, monkeypatch):
    """Auth ativada (LF_API_REQUIRE_AUTH=true + LF_API_API_KEY) em tmp_path.

    O APISettings usa env_prefix "LF_API_", então a chave lida pelo pydantic é
    LF_API_API_KEY (mesma convenção usada por lf serve — cli/commands/serve.py).
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", KEY)
    await init_db()
    yield
    await close_db()


@pytest.mark.asyncio
async def test_v1_routers_401_sem_key():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Trajectories (todas as rotas de leitura/escrita)
        assert (await ac.get("/api/v1/trajectories/x/checkpoints")).status_code == 401
        assert (await ac.get("/api/v1/trajectories/x/checkpoints/c1")).status_code == 401
        assert (await ac.get("/api/v1/trajectories/x/export")).status_code == 401
        assert (await ac.post("/api/v1/trajectories/import", json={})).status_code == 401
        assert (await ac.post("/api/v1/trajectories/x/fork")).status_code == 401

        # MCP
        assert (await ac.get("/api/v1/mcp/servers")).status_code == 401
        assert (await ac.get("/api/v1/mcp/servers/x/tools")).status_code == 401

        # Providers
        assert (await ac.get("/api/v1/providers/ollama/models")).status_code == 401

        # Config (GET e PATCH)
        assert (await ac.get("/api/v1/config")).status_code == 401
        assert (await ac.patch("/api/v1/config", json={})).status_code == 401


@pytest.mark.asyncio
async def test_v1_routers_200_com_key(monkeypatch):
    # Providers: mock do Ollama para a rota responder 200 (sem Ollama real).
    class _FakeOllama:
        def discover_models(self):
            return []

    monkeypatch.setattr("lf.api.providers.OllamaProvider", lambda **kw: _FakeOllama())

    app = create_app()
    headers = {"X-API-Key": KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/trajectories/x/checkpoints", headers=headers)).status_code == 200
        assert (await ac.get("/api/v1/mcp/servers", headers=headers)).status_code == 200
        assert (await ac.get("/api/v1/providers/ollama/models", headers=headers)).status_code == 200
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 200
        assert (await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": 60}}, headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_key_errada_401():
    app = create_app()
    headers = {"X-API-Key": "chave-errada"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 401
