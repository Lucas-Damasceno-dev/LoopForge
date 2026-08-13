"""Per-run LLM model via API (POST /api/v1/runs campo `model`).

Verifica o caminho completo: payload RunCreate.model → fila E3 → TaskSchema.model
→ _build_initial_state.llm_model_name. mock_llm=true p/ determinismo; o dispatch
é espionado (não executa o grafo de verdade).
"""

import asyncio
import contextlib
import os
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest_asyncio.fixture(autouse=True)
async def api_env(tmp_path, monkeypatch):
    from lf.api.database import Base, engine

    monkeypatch.chdir(tmp_path)
    env_backup = {k: os.environ.get(k) for k in ("OPENROUTER_MODEL", "OPENCODE_MODEL")}
    for k in env_backup:
        os.environ.pop(k, None)
    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    for k, v in env_backup.items():
        if v is not None:
            os.environ[k] = v
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


async def _create_run(client: AsyncClient, **extra) -> dict:
    payload = {"idea": "Run com model", "mock_llm": True, **extra}
    resp = await client.post("/api/v1/runs", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_post_run_com_model_chega_no_task():
    captured: list[TaskSchema] = []

    def _spy_dispatch(self, task, project_id="project", shared_state=None):
        captured.append(task)
        # Não executa o grafo: retorna estado mínimo (mock determinístico).
        return {"idea": task.title, "error": None}

    app = create_app()
    with patch.object(TaskDispatcher, "dispatch", new=_spy_dispatch):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            run = await _create_run(client, model="meu-modelo-teste")
            assert run["id"]
            # dá tempo da fila E3 promover e o dispatch espionado rodar
            for _ in range(50):
                if captured:
                    break
                await asyncio.sleep(0.1)

    assert captured, "dispatch não foi chamado com a run model"
    task = captured[-1]
    assert task.model == "meu-modelo-teste"


@pytest.mark.asyncio
async def test_post_run_sem_model_default_none():
    captured: list[TaskSchema] = []

    def _spy_dispatch(self, task, project_id="project", shared_state=None):
        captured.append(task)
        return {"idea": task.title, "error": None}

    app = create_app()
    with patch.object(TaskDispatcher, "dispatch", new=_spy_dispatch):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await _create_run(client)
            for _ in range(50):
                if captured:
                    break
                await asyncio.sleep(0.1)

    assert captured, "dispatch não foi chamado"
    assert captured[-1].model is None


def test_build_initial_state_preenche_llm_model_name(tmp_path, monkeypatch):
    monkeypatch.setenv("LF_WORKDIR_BASE", str(tmp_path / "workbase"))
    dispatcher = TaskDispatcher(mock_llm=True)

    task_com_model = TaskSchema(id="m-1", title="t", stack="python", model="meu-modelo-teste")
    state = dispatcher._build_initial_state(task_com_model, "proj-m")
    assert state["llm_model_name"] == "meu-modelo-teste"

    task_sem_model = TaskSchema(id="m-2", title="t", stack="python")
    state2 = dispatcher._build_initial_state(task_sem_model, "proj-m")
    assert state2["llm_model_name"] is None
