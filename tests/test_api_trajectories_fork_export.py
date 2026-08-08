"""Testes M-13/M-14: fork REAL, export enriquecido e import materializador.

Usa o padrão endurecido de test_event_envelope (LF_API_TEST=1 + init_db) para
que o EventBus persista o journal (evento ``fork_created``) no banco de teste
e o ledger llm_costs seja visível para o export. Cada teste roda em tmp_path
hermético (trajectories.db, telemetry.sqlite e test_api.sqlite em .loopforge/).
"""

import contextlib
import os
import sqlite3
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.api.events import event_bus


async def _seed_thread(thread_id: str, checkpoint_ids: tuple[str, ...], states: list[dict]) -> None:
    """Grava checkpoints direto no checkpointer (sem passar pela API)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        for i, cid in enumerate(checkpoint_ids):
            await saver.aput(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
                {
                    "id": cid,
                    "v": 1,
                    "ts": f"2026-08-05T00:00:{i:02d}Z",
                    "channel_values": states[i],
                },
                {"source": "loop", "step": i},
                {},
            )
    finally:
        await saver.conn.close()


def _insert_parent_run(run_id: str, idea: str) -> None:
    """Cria a run pai em pipeline_runs (mesmo schema do dispatcher)."""
    db_path = Path(".loopforge/telemetry.sqlite").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS pipeline_runs (
                id VARCHAR(36) PRIMARY KEY, idea TEXT NOT NULL,
                stack VARCHAR(50) DEFAULT 'python', status VARCHAR(20) DEFAULT 'pending',
                current_node VARCHAR(50), logs TEXT, duration_seconds FLOAT DEFAULT 0.0,
                thread_id VARCHAR(50), parent_run_id VARCHAR(36),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_runs (id, idea, stack, status, thread_id) "
            "VALUES (?, ?, 'python', 'completed', ?)",
            (run_id, idea, f"run-{run_id}"),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_llm_costs(run_id: str, rows: list[tuple]) -> None:
    """Insere linhas no ledger llm_costs (mesmo schema do CostTracker)."""
    db_path = Path(".loopforge/telemetry.sqlite").resolve()
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS llm_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_id TEXT, node TEXT, estimated INTEGER DEFAULT 0)"""
        )
        conn.executemany(
            "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd, run_id, node, estimated) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _fetch_pipeline_run(fork_run_id: str) -> tuple | None:
    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        return conn.execute(
            "SELECT id, status, thread_id, parent_run_id, idea FROM pipeline_runs WHERE id = ?",
            (fork_run_id,),
        ).fetchone()
    finally:
        conn.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    """Banco SQLite limpo em tmp_path para cada teste (LF_API_TEST=1)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()
    # Garante que nenhum WAL órfão polua o próximo teste da suíte.
    for f in (".loopforge/test_api.sqlite-wal", ".loopforge/test_api.sqlite-shm"):
        with contextlib.suppress(Exception):
            os.remove(f)
    monkeypatch.delenv("LF_API_TEST", raising=False)


@pytest.mark.asyncio
async def test_fork_real_copia_checkpoints_e_registra_pipeline_run():
    """(a) Fork REAL: copia N checkpoints, origem intacta, run filha e evento no journal."""
    run_id = str(uuid.uuid4())
    thread = f"run-{run_id}"
    states = [
        {"next_agent": "cpo", "idea": "ideia original"},
        {"next_agent": "pm", "idea": "ideia original"},
    ]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)
    _insert_parent_run(run_id, "ideia original")

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/v1/trajectories/{thread}/fork")
        assert r.status_code == 201
        data = r.json()
        assert set(data) == {"fork_run_id", "thread_id", "checkpoint_id"}
        assert data["thread_id"].startswith("run-")
        assert data["checkpoint_id"] == "seed-2"  # head (ORDEM DESC do saver)

        child_thread = data["thread_id"]
        fork_run_id = data["fork_run_id"]

        # thread filha listável com os 2 checkpoints copiados
        rl = await ac.get(f"/api/v1/trajectories/{child_thread}/checkpoints")
        assert rl.status_code == 200
        assert rl.json() == [{"thread_id": child_thread}]
        for cid in ("seed-1", "seed-2"):
            rc = await ac.get(f"/api/v1/trajectories/{child_thread}/checkpoints/{cid}")
            assert rc.status_code == 200
            assert rc.json()["state"] == states[0 if cid == "seed-1" else 1]

        # origem intacta
        ro = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints")
        assert ro.json() == [{"thread_id": thread}]

        # pipeline_runs: linha filha com parent_run_id + idea herdada
        row = _fetch_pipeline_run(fork_run_id)
        assert row is not None
        assert row[1] == "queued"
        assert row[2] == child_thread
        assert row[3] == run_id
        assert row[4] == "ideia original"

        # evento fork_created no journal (persistido via EventBus)
        events = await event_bus.list_events(fork_run_id)
        assert any(
            e["event"] == "fork_created"
            and e["payload"]
            == {
                "parent_run_id": run_id,
                "fork_run_id": fork_run_id,
                "checkpoint_id": "seed-2",
            }
            for e in events
        )


@pytest.mark.asyncio
async def test_export_enriquecido_inclui_checkpoints_steps_events_costs():
    """(b) Export enriquecido: campos esperados, events/steps/costs corretos."""
    run_id = str(uuid.uuid4())
    thread = f"run-{run_id}"
    states = [
        {"next_agent": "cpo", "idea": "x"},
        {"next_agent": "pm", "idea": "x"},
    ]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)
    await event_bus.publish(run_id, "run_created", {"status": "queued"})
    await event_bus.publish(run_id, "pipeline_started", {"node": "cpo"})
    _seed_llm_costs(
        run_id,
        [
            ("oc/deepseek", 100, 50, 0.001234, run_id, "cpo", 0),
            ("oc/deepseek", 200, 80, 0.002000, run_id, "pm", 1),
        ],
    )

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/v1/trajectories/export/{run_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["schema_version"] == "1.1"
        assert data["run_id"] == run_id
        assert data["thread_id"] == thread
        assert data["exported_at"]

        # checkpoints serializados (estado completo em JSON, ordem cronológica)
        assert len(data["checkpoints"]) == 2
        first = data["checkpoints"][0]
        assert first["checkpoint_id"] == "seed-1"
        assert first["ts"] == "2026-08-05T00:00:00Z"
        assert first["step"] == 0
        assert first["state"] == states[0]

        # steps derivados por nó
        assert len(data["steps"]) == 2
        assert [s["node"] for s in data["steps"]] == ["cpo", "pm"]
        assert [s["step"] for s in data["steps"]] == [0, 1]

        # events do journal (envelopes v1 em ordem de seq)
        assert [e["event"] for e in data["events"]] == ["run_created", "pipeline_started"]

        # costs do ledger llm_costs (soma + linhas)
        assert data["costs"]["total_usd"] == pytest.approx(0.003234, abs=1e-6)
        assert data["costs"]["estimated"] is True
        assert len(data["costs"]["rows"]) == 2
        assert data["costs"]["rows"][0]["node"] == "cpo"


@pytest.mark.asyncio
async def test_roundtrip_export_import_get_identico():
    """(c) Roundtrip export → import → GET checkpoints idêntico."""
    run_id = str(uuid.uuid4())
    thread = f"run-{run_id}"
    states = [
        {"next_agent": "cpo", "idea": "login"},
        {"next_agent": "qa", "idea": "login"},
    ]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)
    _insert_parent_run(run_id, "login")

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/v1/trajectories/export/{run_id}")
        assert r.status_code == 200
        data = r.json()

        new_thread = "run-import-roundtrip"
        payload = {**data, "thread_id": new_thread}
        r2 = await ac.post("/api/v1/trajectories/import", json=payload)
        assert r2.status_code == 201
        assert r2.json() == {
            "run_id": run_id,
            "thread_id": new_thread,
            "checkpoints_imported": 2,
        }

        for i, cid in enumerate(("seed-1", "seed-2")):
            r3 = await ac.get(f"/api/v1/trajectories/{new_thread}/checkpoints/{cid}")
            assert r3.status_code == 200
            assert r3.json()["state"] == states[i]


@pytest.mark.asyncio
async def test_import_invalido_422():
    """(d) Import inválido → 422 (estrutura malformada / schema fora do suportado)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # body não-objeto (lista) → 422 do FastAPI
        r = await ac.post("/api/v1/trajectories/import", json=[])
        assert r.status_code == 422

        # schema_version fora do suportado → 422
        r2 = await ac.post(
            "/api/v1/trajectories/import",
            json={"schema_version": "1.0", "run_id": "x", "thread_id": "y", "checkpoints": []},
        )
        assert r2.status_code == 422

        # sem run_id → 422
        r3 = await ac.post(
            "/api/v1/trajectories/import",
            json={"schema_version": "1.1", "thread_id": "y", "checkpoints": []},
        )
        assert r3.status_code == 422

        # checkpoint sem checkpoint_id → 422
        r4 = await ac.post(
            "/api/v1/trajectories/import",
            json={
                "schema_version": "1.1",
                "run_id": "x",
                "thread_id": "y",
                "checkpoints": [{"ts": "t"}],
            },
        )
        assert r4.status_code == 422


@pytest.mark.asyncio
async def test_fork_run_inexistente_404():
    """(e) Fork de run inexistente → 404."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/v1/trajectories/run-{uuid.uuid4()}/fork")
        assert r.status_code == 404
