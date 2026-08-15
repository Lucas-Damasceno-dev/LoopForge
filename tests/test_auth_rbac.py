"""Testes RBAC (Tier2): roles por API key — admin / runner / viewer.

Cobre: BC do env LF_API_KEY (single key = admin), keys do ade.yaml com roles,
401 (key desconhecida / sem key) vs 403 (role insuficiente), e a matriz
path→role via _required_role. WS mantém o token check legado no app.py
(single key) — fora do escopo desta lane.
"""

import pytest
import pytest_asyncio
import yaml
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.auth import _required_role, get_principal
from lf.api.config import APISettings
from lf.api.database import close_db, init_db

ENV_KEY = "env-admin-key-123"
RUNNER_KEY = "runner-key-456"
VIEWER_KEY = "viewer-key-789"
NO_ROLES_KEY = "no-roles-key-000"


def _write_ade(tmp_path, keys: list[dict]) -> None:
    """Escreve .loopforge/ade.yaml com o bloco api_keys."""
    d = tmp_path / ".loopforge"
    d.mkdir(exist_ok=True)
    (d / "ade.yaml").write_text(yaml.safe_dump({"api_keys": keys}), encoding="utf-8")


@pytest_asyncio.fixture(autouse=True)
async def setup_rbac_env(tmp_path, monkeypatch):
    """Auth ativada + env key admin (BC) + DB limpo."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", ENV_KEY)
    await init_db()
    yield
    await close_db()


def _ade_keys() -> list[dict]:
    return [
        {"name": "runner-svc", "key": RUNNER_KEY, "roles": ["runner"]},
        {"name": "viewer-svc", "key": VIEWER_KEY, "roles": ["viewer"]},
        {"name": "no-roles", "key": NO_ROLES_KEY},
    ]


@pytest.mark.asyncio
async def test_env_key_admin_bc(tmp_path):
    """BC: sem ade.yaml, env key única tem acesso total (admin)."""
    app = create_app()
    headers = {"X-API-Key": ENV_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 200
        assert (
            await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": 60}}, headers=headers)
        ).status_code == 200


@pytest.mark.asyncio
async def test_sem_key_401(tmp_path):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config")).status_code == 401


@pytest.mark.asyncio
async def test_key_desconhecida_401(tmp_path):
    app = create_app()
    headers = {"X-API-Key": "chave-que-nao-existe"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_viewer_403_em_rotas_admin(tmp_path):
    """Viewer bloqueado em config/mcp (admin); liberado em leitura (trajectories)."""
    _write_ade(tmp_path, _ade_keys())
    app = create_app()
    headers = {"X-API-Key": VIEWER_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Admin exigido → 403 (não 401: key é conhecida)
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 403
        assert (await ac.patch("/api/v1/config", json={}, headers=headers)).status_code == 403
        assert (await ac.get("/api/v1/mcp/servers", headers=headers)).status_code == 403
        # Leitura viewer → 200
        assert (await ac.get("/api/v1/trajectories/x/checkpoints", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_runner_403_admin_200_runner(tmp_path):
    """Runner bloqueado em config (admin) e liberado para criar run (runner)."""
    _write_ade(tmp_path, _ade_keys())
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Admin exigido → 403
        assert (await ac.get("/api/v1/config", headers={"X-API-Key": RUNNER_KEY})).status_code == 403
        # Runner permite POST /api/v1/runs
        resp = await ac.post(
            "/api/v1/runs",
            json={"idea": "RBAC runner", "stack": "python", "mock_llm": True},
            headers={"X-API-Key": RUNNER_KEY},
        )
        assert resp.status_code == 201
        # Viewer NÃO pode criar run → 403
        resp = await ac.post(
            "/api/v1/runs",
            json={"idea": "RBAC viewer", "stack": "python", "mock_llm": True},
            headers={"X-API-Key": VIEWER_KEY},
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_key_sem_roles_default_admin(tmp_path):
    """Key sem campo roles no ade.yaml → default admin (BC)."""
    _write_ade(tmp_path, _ade_keys())
    app = create_app()
    headers = {"X-API-Key": NO_ROLES_KEY}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config", headers=headers)).status_code == 200
        assert (
            await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": 60}}, headers=headers)
        ).status_code == 200


@pytest.mark.asyncio
async def test_basic_auth_com_key_aceita(tmp_path):
    """Basic auth legado: key no username também resolve (BC)."""
    app = create_app()
    auth = ("env-admin-key-123", "x")  # username = key
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/config", auth=auth)).status_code == 200


def test_get_principal_helper():
    """Helper público resolve env key → Principal admin."""
    principal = get_principal(ENV_KEY, APISettings())
    assert principal is not None
    assert principal.name == "api-key-env"
    assert "admin" in principal.roles


@pytest.mark.asyncio
async def test_auth_me_retorna_principal(tmp_path):
    """/auth/me devolve name+roles do principal da key."""
    _write_ade(tmp_path, _ade_keys())
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me", headers={"X-API-Key": RUNNER_KEY})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "runner-svc"
        assert body["roles"] == ["runner"]


@pytest.mark.asyncio
async def test_auth_me_env_key_admin(tmp_path):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me", headers={"X-API-Key": ENV_KEY})
        assert r.status_code == 200
        assert r.json()["roles"] == ["admin"]


@pytest.mark.asyncio
async def test_auth_me_sem_key_401(tmp_path):
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        assert (await ac.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_auth_me_auth_off_anonymous_admin(tmp_path, monkeypatch):
    """Auth desativada → principal anônimo admin (BC: UI assume admin)."""
    monkeypatch.delenv("LF_API_API_KEY", raising=False)
    monkeypatch.delenv("LF_API_REQUIRE_AUTH", raising=False)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/auth/me")
        assert r.status_code == 200
        assert r.json() == {"name": "anonymous", "roles": ["admin"]}


def test_matriz_roles():
    """Matriz path→role: admin > runner > viewer, default viewer p/ leituras."""
    # Admin
    assert _required_role("GET", "/api/v1/config") == "admin"
    assert _required_role("PATCH", "/api/v1/config") == "admin"
    assert _required_role("GET", "/api/v1/mcp/servers") == "admin"
    assert _required_role("POST", "/api/v1/mcp/servers/x/tools/git") == "admin"
    assert _required_role("GET", "/api/v1/runs/abc/cost") == "admin"
    assert _required_role("POST", "/api/v1/runs/abc/cost/override") == "admin"
    assert _required_role("PATCH", "/api/v1/prompts/system") == "admin"
    assert _required_role("DELETE", "/api/v1/prompts/system") == "admin"
    assert _required_role("DELETE", "/api/v1/memory/lessons/l1") == "admin"
    assert _required_role("DELETE", "/api/runs/abc") == "admin"
    # D11: matriz cobre o prefixo v1 (/api/v1/runs) na MESMA regra
    assert _required_role("DELETE", "/api/v1/runs/abc") == "admin"
    # Runner
    assert _required_role("POST", "/api/v1/runs") == "runner"
    assert _required_role("POST", "/api/runs") == "runner"
    assert _required_role("POST", "/api/v1/runs/abc/resume") == "runner"
    assert _required_role("POST", "/api/runs/abc/execute") == "runner"
    assert _required_role("POST", "/api/v1/runs/abc/decide") == "runner"
    assert _required_role("POST", "/api/v1/runs/abc/cancel") == "runner"  # C8
    assert _required_role("PATCH", "/api/runs/abc") == "runner"
    assert _required_role("PATCH", "/api/v1/runs/abc") == "runner"  # D11
    assert _required_role("POST", "/api/v1/trajectories/import") == "runner"
    assert _required_role("POST", "/api/v1/trajectories/abc/fork") == "runner"
    assert _required_role("POST", "/api/v1/memory/lessons") == "runner"
    assert _required_role("PATCH", "/api/v1/memory/lessons/l1") == "runner"
    # Viewer (default p/ leituras)
    assert _required_role("GET", "/api/v1/evals/summary") == "viewer"
    assert _required_role("GET", "/api/v1/git/status") == "viewer"
    assert _required_role("GET", "/api/v1/runs/abc/timeline") == "viewer"
    assert _required_role("GET", "/api/v1/trajectories/abc/export") == "viewer"
    # Escrita não mapeada → runner (default seguro)
    assert _required_role("POST", "/api/v1/rota-futura") == "runner"
