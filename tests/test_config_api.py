"""Testes da Config API: GET/PATCH /api/v1/config sobre .loopforge/ade.yaml."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.config.loader import load_ade_config


@pytest.mark.asyncio
async def test_config_get_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/config")
        assert r.status_code == 200
        assert r.json()["hitl"]["timeout_seconds"] == 300


@pytest.mark.asyncio
async def test_config_patch_persists_and_reloads(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": 60}})
        assert r.status_code == 200
        assert r.json()["hitl"]["timeout_seconds"] == 60
    reloaded = load_ade_config(Path(".loopforge/ade.yaml"))
    assert reloaded.hitl.timeout_seconds == 60


@pytest.mark.asyncio
async def test_config_patch_invalid_does_not_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".loopforge").mkdir(exist_ok=True)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": "abc"}})
        assert r.status_code == 422
    assert not (tmp_path / ".loopforge" / "ade.yaml").exists()


@pytest.mark.asyncio
async def test_config_patch_mcp_servers_valid_invalid(tmp_path, monkeypatch):
    """D3 (Fase D): PATCH /config valida mcp_servers como list[AdeMcpServer].

    Válido (toggle enabled=false) persiste; inválido → 422 SEM corromper o
    ade.yaml (o último estado válido é preservado).
    """
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Válido: lista de dicts reconstruída como list[AdeMcpServer] validado
        r = await ac.patch(
            "/api/v1/config",
            json={
                "mcp_servers": [
                    {
                        "name": "fs",
                        "command": "npx",
                        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                        "tools_allowlist": ["read_file"],
                        "enabled": False,
                    }
                ]
            },
        )
        assert r.status_code == 200
        servers = r.json()["mcp_servers"]
        assert servers[0]["name"] == "fs"
        assert servers[0]["enabled"] is False
        assert servers[0]["command"] == "npx"

        # Persistido no ade.yaml (reload preserva o toggle)
        reloaded = load_ade_config(Path(".loopforge/ade.yaml"))
        assert reloaded.mcp_servers[0].enabled is False
        assert reloaded.mcp_servers[0].tools_allowlist == ["read_file"]

        # Inválido: item sem `command` (obrigatório) → 422 com detalhes
        r2 = await ac.patch("/api/v1/config", json={"mcp_servers": [{"name": "sem-command"}]})
        assert r2.status_code == 422
        detail = str(r2.json()["detail"])
        assert "command" in detail

        # O arquivo NÃO foi corrompido pelo PATCH inválido
        reloaded2 = load_ade_config(Path(".loopforge/ade.yaml"))
        assert reloaded2.mcp_servers[0].name == "fs"

        # Inválido: item não-dict na lista → 422
        r3 = await ac.patch("/api/v1/config", json={"mcp_servers": ["nao-sou-dict"]})
        assert r3.status_code == 422
