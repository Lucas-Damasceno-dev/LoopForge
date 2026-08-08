"""E2E resume via API (M-01/A9 da Fase A — ADR-0003).

Sem o fix, o dispatch criava a thread `run-{uuid}-task-{uuid[:8]}` e o resume
via API procurava `project-run-{uuid}` — nunca casava. Com a correção, o
dispatch usa a thread canônica `run-{run_id}` persistida em
`pipeline_runs.thread_id` e o resume lê a coluna, encontrando a thread real em
trajectories.db.
"""

import asyncio
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.orchestrator.task_dispatcher import TaskDispatcher


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    """Banco SQLite limpo em tmp_path (mesmo padrão de test_api.py)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


async def _wait_status(client: AsyncClient, run_id: str, timeout: float = 30.0) -> str:
    """Poll GET /api/runs/{id} até a run sair de pending/running."""
    waited = 0.0
    status = "pending"
    while waited < timeout:
        resp = await client.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        status = resp.json()["status"]
        if status in ("completed", "failed"):
            return status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em {timeout}s (status: {status})")


@pytest.mark.asyncio
async def test_resume_api_finds_persisted_thread():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        resp = await client.post(
            "/api/runs",
            json={"idea": "Build resume e2e", "stack": "python", "mock_llm": True},
        )
        assert resp.status_code == 201
        run_id = resp.json()["id"]
        expected_thread = f"run-{run_id}"

        # 1. Dispatch em background conclui e cria a thread canônica em trajectories.db
        status = await _wait_status(client, run_id)
        assert status in ("completed", "failed"), f"status inesperado: {status}"

        # A thread real existe no formato 'run-{id}' (ADR-0003).
        # list_checkpoints usa asyncio.run internamente — roda em to_thread.
        dispatcher = TaskDispatcher(mock_llm=True)
        checkpoints = await asyncio.to_thread(dispatcher.list_checkpoints)
        assert expected_thread in checkpoints, (
            f"thread {expected_thread} não encontrada em trajectories.db: {checkpoints}"
        )

        # 2. Resume via API usa o thread_id persistido e encontra a thread
        resume_resp = await client.post(f"/api/runs/{run_id}/resume")
        assert resume_resp.status_code == 200

        # Aguarda o resume em background finalizar (marca logs de sucesso).
        waited = 0.0
        data: dict = {}
        while waited < 15.0:
            await asyncio.sleep(0.2)
            r = await client.get(f"/api/runs/{run_id}")
            data = r.json()
            if data["logs"] and "retomada" in data["logs"]:
                break
            if data["status"] == "failed":
                break
            waited += 0.2
        assert data.get("status") != "failed", f"resume falhou: {data}"
        assert data.get("logs") and "retomada" in data["logs"], (
            f"resume não concluiu via thread persistida: {data}"
        )
