"""Testes de integração do roteamento de APIs (artifacts, AST, coverage, terminal) para worktree."""

import contextlib
import os
from pathlib import Path
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert

from lf.api.app import create_app
import lf.api.database as db
from lf.api.models import PipelineRun

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_env():
    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)
    await db.init_db()
    if db.engine is not None:
        async with db.engine.begin() as conn:
            await conn.run_sync(db.Base.metadata.drop_all)
            await conn.run_sync(db.Base.metadata.create_all)
    yield
    await db.close_db()
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


def _client():
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_apis_route_to_slim_worktree():
    run_id = "99999999-aaaa-bbbb-cccc-dddddddddddd"

    # Insere run no DB
    assert db.engine is not None
    async with db.engine.begin() as conn:
        await conn.execute(
            insert(PipelineRun).values(
                id=run_id,
                idea="Worktree Routing Test",
                stack="python",
                status="completed",
            )
        )

    # Cria worktree simulada em .slim/worktrees/run_<run_id>
    wt_dir = Path(f".slim/worktrees/run_{run_id}")
    wt_dir.mkdir(parents=True, exist_ok=True)

    py_file = wt_dir / "calculator.py"
    py_file.write_text("class Calculator:\n    def add(self, a: int, b: int) -> int:\n        return a + b\n")

    try:
        async with _client() as client:
            # 1. Artifacts Files
            art_resp = await client.get(f"/api/v1/runs/{run_id}/files")
            assert art_resp.status_code == 200
            art_data = art_resp.json()
            assert any(f["path"] == "calculator.py" for f in art_data["files"])

            # 2. AST Analyzer
            ast_resp = await client.get(f"/api/v1/ast/{run_id}")
            assert ast_resp.status_code == 200
            ast_data = ast_resp.json()
            assert any(m["file_path"] == "calculator.py" for m in ast_data["modules"])
            calc_mod = next(m for m in ast_data["modules"] if m["file_path"] == "calculator.py")
            assert any(s["name"] == "Calculator" for s in calc_mod["symbols"])

            # 3. Terminal Info & Exec
            term_info = await client.get(f"/api/v1/terminal/{run_id}/info")
            assert term_info.status_code == 200
            assert term_info.json()["exists"] is True
            assert str(wt_dir.resolve()) in term_info.json()["workspace_path"]

            term_exec = await client.post(
                f"/api/v1/terminal/{run_id}/exec",
                json={"command": "cat calculator.py", "timeout_seconds": 5},
            )
            assert term_exec.status_code == 200
            assert "class Calculator:" in term_exec.json()["stdout"]
    finally:
        import shutil

        if wt_dir.exists():
            shutil.rmtree(".slim/worktrees")
