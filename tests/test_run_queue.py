"""Testes da fila de execução E3 (M-21/A8): N runs ativas + FIFO de runs `queued`.

Cobre o requisito do plano: 2º POST /runs com o 1º ainda ativo nasce `queued`
e não executa até o 1º terminar (aqui com max_concurrent_runs=1 injetado); ao
terminar, o worker promove a próxima.
Também verifica os eventos run_updated publicados via EventBus em cada transição.
"""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.api.events import event_bus
from lf.config.schema import AdeConfig, AdeRunner


@pytest_asyncio.fixture(autouse=True)
async def setup_queue_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    # E3: este teste pinna a semântica antiga (1 run ativa) — o default do
    # config é 2 concorrentes (test_parallel_runs.py cobre o paralelismo real).
    # Patching no módulo loader: create_app faz `from lf.config.loader import
    # load_ade_config` em call-time, então o atributo do módulo é o alvo certo.
    monkeypatch.setattr(
        "lf.config.loader.load_ade_config",
        lambda: AdeConfig(runner=AdeRunner(max_concurrent_runs=1)),
    )
    await init_db()
    yield
    await close_db()


async def _wait_status(ac: AsyncClient, run_id: str, statuses: set[str], timeout: float = 60.0) -> str:
    """Poll GET /api/runs/{id} até o status entrar no conjunto esperado."""
    waited = 0.0
    while waited < timeout:
        resp = await ac.get(f"/api/runs/{run_id}")
        assert resp.status_code == 200
        status = resp.json()["status"]
        if status in statuses:
            return status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não atingiu {statuses} em {timeout}s (último: {status})")


@pytest.mark.asyncio
async def test_second_run_queued_until_first_finishes():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        # 1ª run: fila vazia -> promovida a running na criação (await no handler)
        r1 = await ac.post("/api/runs", json={"idea": "Run 1", "stack": "python", "mock_llm": True})
        assert r1.status_code == 201
        run1 = r1.json()
        assert run1["status"] == "running"
        run1_id = run1["id"]

        # 2ª run com a 1ª ativa -> nasce queued e NÃO executa até a 1ª terminar
        r2 = await ac.post("/api/runs", json={"idea": "Run 2", "stack": "python", "mock_llm": True})
        assert r2.status_code == 201
        run2 = r2.json()
        assert run2["status"] == "queued"
        run2_id = run2["id"]

        # Estado da fila (determinístico): run1 ativa, run2 aguardando
        q = app.state.run_queue
        assert q.active == {run1_id}, f"ativa deveria ser run1, é {q.active}"
        assert run2_id in q.pending, "run2 deveria estar na fila"

        # persistido no DB: GET reflete queued
        assert (await ac.get(f"/api/runs/{run2_id}")).json()["status"] == "queued"

        # Espera a 1ª terminar (a 2ª só então é promovida)
        status1 = await _wait_status(ac, run1_id, {"completed", "failed"})
        assert status1 in ("completed", "failed")

        # Após a 1ª terminar, a 2ª promove a running e executa até o fim
        status2 = await _wait_status(ac, run2_id, {"running", "completed", "failed"})
        assert status2 == "running", f"run2 deveria promover a running, está {status2}"
        final2 = await _wait_status(ac, run2_id, {"completed", "failed"})
        assert final2 == "completed", f"run2 deveria completar, está {final2}"

        # Eventos run_updated publicados via EventBus em cada transição da run2
        events = await event_bus.list_events(run2_id)
        statuses = [e["payload"].get("status") for e in events if e["event"] == "run_updated"]
        assert statuses[0] == "queued", f"primeiro run_updated deveria ser queued: {statuses}"
        assert "running" in statuses, f"esperava transição running: {statuses}"
        assert statuses[-1] == "completed", f"último run_updated deveria ser completed: {statuses}"
