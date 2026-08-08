"""Testes das rotas de Trajectories (checkpoints + export/import/fork) da ADE.

Cobre o contrato da Fase 1 renovado pelas tasks M-13/M-14: fork REAL (copia
checkpoints para ``run-{fork_uuid}``), export enriquecido (POST /export/{run_id})
e import materializador (recria os checkpoint tuples na thread). Os cenários
com journal de eventos vivem em test_api_trajectories_fork_export.py (que
inicializa o banco do EventBus via LF_API_TEST); aqui os testes são herméticos
em tmp_path sem DB do EventBus.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app


async def _seed_thread(
    thread_id: str,
    checkpoint_ids: tuple[str, ...] = ("seed-1",),
    states: list[dict] | None = None,
) -> None:
    """Grava checkpoints direto no checkpointer (sem passar pela API)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        for i, cid in enumerate(checkpoint_ids):
            state = states[i] if states else {"next_agent": "cpo"}
            await saver.aput(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
                {
                    "id": cid,
                    "v": 1,
                    "ts": f"2026-08-05T00:00:{i:02d}Z",
                    "channel_values": state,
                },
                {"source": "loop", "step": i},
                {},
            )
    finally:
        await saver.conn.close()


async def _fork(ac, thread_id: str):
    return await ac.post(f"/api/v1/trajectories/{thread_id}/fork")


@pytest.mark.asyncio
async def test_trajectories_export_import_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    run_id = "11111111-2222-3333-4444-555555555555"
    thread = f"run-{run_id}"
    states = [
        {"next_agent": "cpo", "idea": "fazer login"},
        {"next_agent": "pm", "idea": "fazer login"},
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _seed_thread(thread, ("seed-1", "seed-2"), states)

        # lista de checkpoints da thread
        r0 = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints")
        assert r0.status_code == 200
        assert r0.json() == [{"thread_id": thread}]

        # checkpoint por id
        r1 = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints/seed-1")
        assert r1.status_code == 200
        data = r1.json()
        assert data["thread_id"] == thread
        assert data["checkpoint_id"] == "seed-1"
        assert data["state"] == states[0]

        # export enriquecido (POST /export/{run_id})
        r = await ac.post(f"/api/v1/trajectories/export/{run_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["schema_version"] == "1.1"
        assert data["run_id"] == run_id
        assert data["thread_id"] == thread
        assert data["exported_at"]
        assert len(data["checkpoints"]) == 2
        assert {c["checkpoint_id"] for c in data["checkpoints"]} == {"seed-1", "seed-2"}
        assert len(data["steps"]) == 2

        # import em thread nova (roundtrip materializa os checkpoints)
        payload = {**data, "thread_id": "run-import-copy"}
        r2 = await ac.post("/api/v1/trajectories/import", json=payload)
        assert r2.status_code == 201
        assert r2.json() == {
            "run_id": run_id,
            "thread_id": "run-import-copy",
            "checkpoints_imported": 2,
        }

        # roundtrip idêntico: estado do checkpoint importado
        r3 = await ac.get("/api/v1/trajectories/run-import-copy/checkpoints/seed-1")
        assert r3.status_code == 200
        assert r3.json()["state"] == states[0]


@pytest.mark.asyncio
async def test_trajectories_import_conflict_and_bad_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    run_id = "22222222-3333-4444-5555-666666666666"
    thread = f"run-{run_id}"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _seed_thread(thread, ("seed-1",), [{"next_agent": "cpo"}])

        # schema inválido → 422
        r = await ac.post(
            "/api/v1/trajectories/import",
            json={"schema_version": "9.9", "run_id": "x", "thread_id": "y", "checkpoints": []},
        )
        assert r.status_code == 422

        # estrutura incompleta → 422
        r5 = await ac.post("/api/v1/trajectories/import", json={})
        assert r5.status_code == 422

        # thread já existe → 409
        r2 = await ac.post(
            "/api/v1/trajectories/import",
            json={
                "schema_version": "1.1",
                "run_id": run_id,
                "thread_id": thread,
                "checkpoints": [],
            },
        )
        assert r2.status_code == 409

        # checkpoint inexistente → 404
        r3 = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints/nao-existe")
        assert r3.status_code == 404

        # export de run inexistente → 404 (rota canônica POST e alias GET)
        r4 = await ac.post("/api/v1/trajectories/export/run-inexistente")
        assert r4.status_code == 404
        r6 = await ac.get("/api/v1/trajectories/thread-inexistente/export")
        assert r6.status_code == 404


@pytest.mark.asyncio
async def test_trajectories_fork(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    run_id = "33333333-4444-5555-6666-777777777777"
    thread = f"run-{run_id}"
    states = [
        {"next_agent": "cpo", "idea": "fork me"},
        {"next_agent": "pm", "idea": "fork me"},
    ]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _seed_thread(thread, ("seed-1", "seed-2"), states)

        r = await _fork(ac, thread)
        assert r.status_code == 201
        data = r.json()
        assert data["fork_run_id"]
        assert data["thread_id"].startswith("run-")
        assert data["checkpoint_id"] == "seed-2"  # head (ORDEM DESC do saver)

        # thread filha listável e origem intacta
        child_thread = data["thread_id"]
        r_list = await ac.get(f"/api/v1/trajectories/{child_thread}/checkpoints")
        assert r_list.status_code == 200
        assert r_list.json() == [{"thread_id": child_thread}]
        r_origin = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints")
        assert r_origin.status_code == 200
        assert r_origin.json() == [{"thread_id": thread}]

        # estado idêntico na filha
        r_cp = await ac.get(f"/api/v1/trajectories/{child_thread}/checkpoints/seed-1")
        assert r_cp.status_code == 200
        assert r_cp.json()["state"] == states[0]

        # pipeline_runs: linha filha com parent_run_id (escrita direta em telemetry)
        import sqlite3

        conn = sqlite3.connect(".loopforge/telemetry.sqlite")
        try:
            row = conn.execute(
                "SELECT status, thread_id, parent_run_id FROM pipeline_runs WHERE id = ?",
                (data["fork_run_id"],),
            ).fetchone()
        finally:
            conn.close()
        assert row is not None
        assert row[0] == "queued"
        assert row[1] == child_thread
        assert row[2] == run_id

        # fork de run inexistente → 404
        r404 = await _fork(ac, "run-inexistente")
        assert r404.status_code == 404
