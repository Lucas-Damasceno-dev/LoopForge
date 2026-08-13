"""Testes unitários e de integração para os endpoints de Terminal, AST e Coverage."""

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
async def test_terminal_api():
    async with _client() as client:
        # Cria a run
        resp = await client.post("/api/runs", json={"idea": "Test Terminal", "stack": "python", "mock_llm": True})
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        run_dir = Path(f"/tmp/loopforge/run_{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        test_file = run_dir / "sample.txt"
        test_file.write_text("Hello from LoopForge Terminal!\n")

        try:
            # Info
            info_resp = await client.get(f"/api/v1/terminal/{run_id}/info")
            assert info_resp.status_code == 200
            info_data = info_resp.json()
            assert info_data["run_id"] == run_id
            assert info_data["exists"] is True

            # Exec ls / cat
            exec_resp = await client.post(
                f"/api/v1/terminal/{run_id}/exec",
                json={"command": "cat sample.txt", "timeout_seconds": 10},
            )
            assert exec_resp.status_code == 200
            exec_data = exec_resp.json()
            assert exec_data["exit_code"] == 0
            assert "Hello from LoopForge Terminal!" in exec_data["stdout"]

            # Forbidden command
            bad_resp = await client.post(
                f"/api/v1/terminal/{run_id}/exec",
                json={"command": "rm -rf /", "timeout_seconds": 5},
            )
            assert bad_resp.status_code == 400
        finally:
            if run_dir.exists():
                import shutil
                shutil.rmtree(run_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ast_analyzer_api():
    async with _client() as client:
        resp = await client.post("/api/runs", json={"idea": "Test AST", "stack": "python", "mock_llm": True})
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        run_dir = Path(f"/tmp/loopforge/run_{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)
        py_file = run_dir / "service.py"
        py_file.write_text("""
import os
import requests
from pydantic import BaseModel

class UserSchema(BaseModel):
    '''User validation schema.'''
    name: str

def calculate_metric(a: int, b: int) -> int:
    return a + b

async def fetch_remote_data():
    pass
""")

        try:
            ast_resp = await client.get(f"/api/v1/ast/{run_id}")
            assert ast_resp.status_code == 200
            ast_data = ast_resp.json()
            assert ast_data["run_id"] == run_id
            assert len(ast_data["modules"]) >= 1

            mod = ast_data["modules"][0]
            assert mod["file_path"] == "service.py"
            assert mod["language"] == "python"

            symbol_names = [s["name"] for s in mod["symbols"]]
            assert "UserSchema" in symbol_names
            assert "calculate_metric" in symbol_names
            assert "fetch_remote_data" in symbol_names

            assert "requests" in ast_data["external_packages"] or "pydantic" in ast_data["external_packages"]
        finally:
            if run_dir.exists():
                import shutil
                shutil.rmtree(run_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_coverage_api():
    async with _client() as client:
        resp = await client.post("/api/runs", json={"idea": "Test Coverage", "stack": "python", "mock_llm": True})
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        run_dir = Path(f"/tmp/loopforge/run_{run_id}")
        run_dir.mkdir(parents=True, exist_ok=True)

        src_file = run_dir / "calculator.py"
        src_file.write_text("def add(x, y):\n    return x + y\n")
        test_file = run_dir / "test_calculator.py"
        test_file.write_text("def test_add():\n    assert True\n")

        try:
            cov_resp = await client.get(f"/api/v1/coverage/{run_id}")
            assert cov_resp.status_code == 200
            cov_data = cov_resp.json()
            assert cov_data["run_id"] == run_id
            assert cov_data["total_lines"] > 0
            assert cov_data["coverage_percentage"] >= 0.0
            assert len(cov_data["files"]) >= 1
        finally:
            if run_dir.exists():
                import shutil
                shutil.rmtree(run_dir, ignore_errors=True)
