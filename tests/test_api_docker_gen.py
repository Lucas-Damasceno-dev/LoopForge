"""Testes unitários e de integração para o gerador de configurações Docker e devcontainer."""

import os
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_env(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()
    monkeypatch.delenv("LF_API_TEST", raising=False)


def _client():
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_get_and_save_docker_config():
    async with _client() as client:
        # Cria uma run Python
        resp = await client.post("/api/runs", json={"idea": "API with FastAPI and Postgres", "stack": "python", "mock_llm": True})
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        run_dir = Path(f"/tmp/loopforge/run_{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "main.py").write_text("import sqlalchemy\n")

        try:
            # 1. GET docker config
            get_resp = await client.get(f"/api/v1/docker/{run_id}")
            assert get_resp.status_code == 200
            data = get_resp.json()
            assert data["run_id"] == run_id
            assert "python:3.12" in data["base_image"]
            assert "FROM" in data["dockerfile"]
            assert "uvicorn" in data["dockerfile"]
            assert "services:" in data["docker_compose"]
            assert "db:" in data["docker_compose"]
            assert "vscode" in data["devcontainer"]
            assert 8000 in data["suggested_ports"]

            # 2. POST save docker config
            save_resp = await client.post(
                f"/api/v1/docker/{run_id}/save",
                json={
                    "dockerfile": data["dockerfile"],
                    "docker_compose": data["docker_compose"],
                    "devcontainer": data["devcontainer"],
                    "dockerignore": data["dockerignore"],
                },
            )
            assert save_resp.status_code == 200
            save_data = save_resp.json()
            assert save_data["success"] is True
            assert len(save_data["saved_files"]) == 4
            assert (run_dir / "Dockerfile").exists()
            assert (run_dir / "docker-compose.yml").exists()
            assert (run_dir / ".devcontainer" / "devcontainer.json").exists()
        finally:
            if run_dir.exists():
                import shutil
                shutil.rmtree(run_dir, ignore_errors=True)
