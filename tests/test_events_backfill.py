"""Testes M-06 (A4, n2b): backfill REST de eventos persistidos (envelope v1).

GET /api/v1/runs/{run_id}/events devolve os envelopes v1 em ordem de seq com
paginação ``after_seq``/``limit``; alias legado /api/runs/{id}/events com
Sunset/Deprecation (M-18); 401 sem key quando auth ligada; 404 para run
inexistente.
"""

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_api.py)."""
    from lf.api.database import Base, engine

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
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


async def _run_mock_pipeline(client: AsyncClient, idea: str = "Backfill") -> tuple[str, str]:
    """Cria e espera uma pipeline mock terminar; devolve (run_id, status)."""
    resp = await client.post("/api/runs", json={"idea": idea, "stack": "python", "mock_llm": True})
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    waited = 0.0
    while waited < 30.0:
        status = (await client.get(f"/api/runs/{run_id}")).json()["status"]
        if status in ("completed", "failed", "paused"):
            return run_id, status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em 30s")


@pytest.mark.asyncio
async def test_events_backfill_after_run():
    """Backfill devolve envelopes v1 em ordem de seq com payload correto."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, status = await _run_mock_pipeline(client, idea="Backfill e2e")
        assert status == "completed"

        events = []
        data = {}
        deadline = asyncio.get_running_loop().time() + 5.0
        while asyncio.get_running_loop().time() < deadline:
            resp = await client.get(f"/api/v1/runs/{run_id}/events")
            assert resp.status_code == 200
            data = resp.json()
            events = data.get("events", [])
            updated_statuses = [e["payload"].get("status") for e in events if e["event"] == "run_updated"]
            if "completed" in updated_statuses:
                break
            await asyncio.sleep(0.1)

        assert data["run_id"] == run_id
        assert events, "nenhum evento persistido para a run"

        # Envelope v1 + seq estritamente incremental
        seqs = [e["seq"] for e in events]
        assert seqs == list(range(1, len(seqs) + 1)), f"seq quebrado: {seqs}"
        for ev in events:
            assert set(ev) == {"seq", "event", "run_id", "timestamp", "payload"}
            assert ev["run_id"] == run_id

        # Payload correto por tipo
        created = next(e for e in events if e["event"] == "run_created")
        assert created["payload"]["idea"] == "Backfill e2e"
        assert created["payload"]["status"] == "queued"

        started = next(e for e in events if e["event"] == "pipeline_started")
        assert "task_id" in started["payload"]  # A3: task_id dentro do payload

        updated_statuses = [e["payload"].get("status") for e in events if e["event"] == "run_updated"]
        assert "running" in updated_statuses and "completed" in updated_statuses

        assert any(e["event"] == "pipeline_finished" for e in events)

        # Sem paginação pendente (menos de 200 eventos)
        assert data["next_after_seq"] is None


@pytest.mark.asyncio
async def test_events_pagination_after_seq_limit():
    """Paginação: after_seq/limit fatiando o journal em ordem."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, _ = await _run_mock_pipeline(client, idea="Paginação")

        # Aguarda o journal estabilizar: o status "completed" chega antes do
        # último evento (run_updated/pipeline_finished tardios), o que quebraria
        # a comparação total × seq final nas páginas.
        for _ in range(30):
            todos = (await client.get(f"/api/v1/runs/{run_id}/events")).json()["events"]
            await asyncio.sleep(0.2)
            again = (await client.get(f"/api/v1/runs/{run_id}/events")).json()["events"]
            if len(todos) == len(again):
                break
        total = len(todos)
        assert total > 5, f"esperado journal com vários eventos, veio {total}"

        # Página 1: limit=5 → 5 eventos + next_after_seq=5
        p1 = (await client.get(f"/api/v1/runs/{run_id}/events", params={"limit": 5})).json()
        assert [e["seq"] for e in p1["events"]] == [1, 2, 3, 4, 5]
        assert p1["next_after_seq"] == 5

        # Página 2: after_seq=5, limit=5 → seq 6..10
        p2 = (await client.get(f"/api/v1/runs/{run_id}/events", params={"after_seq": 5, "limit": 5})).json()
        assert [e["seq"] for e in p2["events"]] == [6, 7, 8, 9, 10]
        assert p2["next_after_seq"] == 10

        # Página final: after_seq=10 → resto, next_after_seq=None (acabou)
        p3 = (await client.get(f"/api/v1/runs/{run_id}/events", params={"after_seq": 10, "limit": 5})).json()
        rest = p3["events"]
        assert rest and rest[-1]["seq"] == total
        assert p3["next_after_seq"] is None

        # Concatenar as páginas reconstitui o journal
        concatenated = p1["events"] + p2["events"] + rest
        assert [e["seq"] for e in concatenated] == list(range(1, total + 1))

        # after_seq além do fim → lista vazia
        beyond = (await client.get(f"/api/v1/runs/{run_id}/events", params={"after_seq": 9999})).json()
        assert beyond["events"] == [] and beyond["next_after_seq"] is None


@pytest.mark.asyncio
async def test_events_legacy_alias_headers():
    """Alias legado /api/runs/{id}/events delega com headers Sunset/Deprecation (M-18)."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, _ = await _run_mock_pipeline(client, idea="Alias legado")

        resp = await client.get(f"/api/runs/{run_id}/events")
        assert resp.status_code == 200
        assert resp.headers.get("Sunset") == "2026-12-31"
        assert resp.headers.get("Deprecation") == "true"
        assert resp.json()["run_id"] == run_id
        assert resp.json()["events"]


@pytest.mark.asyncio
async def test_events_401_sem_key(monkeypatch):
    """Auth ligada: GET /events sem X-API-Key → 401."""
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", "segredo")  # APISettings: env_prefix LF_API_
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/runs/qualquer/events")
        assert resp.status_code == 401

        # Com a key correta, o 404 de run inexistente aparece (auth passou)
        ok = await client.get("/api/v1/runs/nao-existe/events", headers={"X-API-Key": "segredo"})
        assert ok.status_code == 404


@pytest.mark.asyncio
async def test_events_404_run_inexistente():
    """GET /events de run inexistente → 404."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/runs/nao-existe/events")
        assert resp.status_code == 404
