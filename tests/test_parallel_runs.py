"""Testes E3: execução paralela real de runs (max_concurrent_runs > 1).

Cobre o requisito do plano: com N slots (default 2), N runs executam ao mesmo
tempo e as demais nascem `queued`, promovendo FIFO conforme slots liberam.
Usa mock_llm (LF_API_TEST) — nenhum subprocesso real é spawnado.
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
async def setup_parallel_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


async def _wait_status(ac: AsyncClient, run_id: str, statuses: set[str], timeout: float = 90.0) -> str:
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
async def test_parallel_runs_default_max_two():
    """Default (max_concurrent_runs=2): 2 runs rodam juntas, a 3ª fica queued."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        # 3 POSTs em sequência: r1 e r2 promovem a running na criação,
        # r3 nasce queued (limite de 2 concorrentes).
        ids: list[str] = []
        for i in range(3):
            resp = await ac.post("/api/runs", json={"idea": f"Run {i + 1}", "stack": "python", "mock_llm": True})
            assert resp.status_code == 201
            body = resp.json()
            ids.append(body["id"])
            expected = "running" if i < 2 else "queued"
            assert body["status"] == expected, f"run {i + 1}: esperado {expected}, veio {body['status']}"

        r1_id, r2_id, r3_id = ids

        # Estado da fila (janela imediatamente após o 3º POST, padrão do
        # test_run_queue): r1 e r2 ativas, r3 aguardando slot.
        q = app.state.run_queue
        assert q.active == {r1_id, r2_id}, f"esperado {{r1,r2}} ativas, veio {q.active}"
        assert r3_id in q.pending, "r3 deveria estar enfileirada"

        # r3 não executa enquanto os 2 slots estiverem ocupados.
        assert (await ac.get(f"/api/runs/{r3_id}")).json()["status"] == "queued"

        # Quando uma das ativas termina, r3 promove a running e completa.
        status1 = await _wait_status(ac, r1_id, {"completed", "failed"})
        assert status1 in ("completed", "failed")
        status3 = await _wait_status(ac, r3_id, {"running", "completed", "failed"})
        assert status3 == "running", f"r3 deveria promover a running, está {status3}"
        final3 = await _wait_status(ac, r3_id, {"completed", "failed"})
        assert final3 == "completed", f"r3 deveria completar, está {final3}"

        # Eventos run_updated da r3: queued -> running -> completed.
        events = await event_bus.list_events(r3_id)
        statuses = [e["payload"].get("status") for e in events if e["event"] == "run_updated"]
        assert statuses[0] == "queued", f"primeiro run_updated deveria ser queued: {statuses}"
        assert "running" in statuses, f"esperava transição running: {statuses}"
        assert statuses[-1] == "completed", f"último run_updated deveria ser completed: {statuses}"


@pytest.mark.asyncio
async def test_parallel_runs_custom_max_three(monkeypatch):
    """max_concurrent_runs=3 (ade.yaml): 3 runs juntas, a 4ª fica queued."""
    monkeypatch.setattr(
        "lf.api.app.load_ade_config",
        lambda: AdeConfig(runner=AdeRunner(max_concurrent_runs=3)),
    )
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        ids: list[str] = []
        for i in range(4):
            resp = await ac.post("/api/runs", json={"idea": f"Run {i + 1}", "stack": "python", "mock_llm": True})
            assert resp.status_code == 201
            body = resp.json()
            ids.append(body["id"])
            expected = "running" if i < 3 else "queued"
            assert body["status"] == expected, f"run {i + 1}: esperado {expected}, veio {body['status']}"

        r1_id, r2_id, r3_id, r4_id = ids

        q = app.state.run_queue
        assert q.active == {r1_id, r2_id, r3_id}, f"esperado {{r1,r2,r3}} ativas, veio {q.active}"
        assert r4_id in q.pending, "r4 deveria estar enfileirada"

        # Ao liberar slot, r4 promove e completa.
        status1 = await _wait_status(ac, r1_id, {"completed", "failed"})
        assert status1 in ("completed", "failed")
        status4 = await _wait_status(ac, r4_id, {"running", "completed", "failed"})
        assert status4 == "running", f"r4 deveria promover a running, está {status4}"
        final4 = await _wait_status(ac, r4_id, {"completed", "failed"})
        assert final4 == "completed", f"r4 deveria completar, está {final4}"
