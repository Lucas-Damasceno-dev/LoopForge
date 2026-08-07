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
