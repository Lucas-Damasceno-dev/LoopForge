"""Testes das rotas de Trajectories (checkpoints + export/import/fork) da ADE."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app


async def _seed_thread(thread_id: str, checkpoint_id: str = "seed-1") -> None:
    """Grava um checkpoint direto no checkpointer (sem passar pela API)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        # setup() (não asetup) e config com checkpoint_ns + checkpoint["id"]
        await saver.setup()
        await saver.aput(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
            {
                "id": checkpoint_id,
                "v": 1,
                "ts": "2026-08-05T00:00:00Z",
                "channel_values": {"next_agent": "cpo"},
            },
            {"source": "loop", "step": 1},
            {},
        )
    finally:
        await saver.conn.close()


@pytest.mark.asyncio
async def test_trajectories_export_import_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # seed: cria thread via checkpointer direto
        await _seed_thread("proj-seed")

        # lista de checkpoints da thread
        r0 = await ac.get("/api/v1/trajectories/proj-seed/checkpoints")
        assert r0.status_code == 200
        assert r0.json() == [{"thread_id": "proj-seed"}]

        # checkpoint por id
        r1 = await ac.get("/api/v1/trajectories/proj-seed/checkpoints/seed-1")
        assert r1.status_code == 200
        data = r1.json()
        assert data["thread_id"] == "proj-seed"
        assert data["checkpoint_id"] == "seed-1"
        assert data["state"] == {"next_agent": "cpo"}

        # export
        r = await ac.get("/api/v1/trajectories/proj-seed/export")
        assert r.status_code == 200
        data = r.json()
        assert data["schema_version"] == "1.0"
        assert data["thread_id"] == "proj-seed"

        # import em thread nova
        r2 = await ac.post("/api/v1/trajectories/import", json={**data, "thread_id": "proj-copy"})
        assert r2.status_code == 201
        assert r2.json()["thread_id"] == "proj-copy"

        # artefato de import persistido
        meta = Path(".loopforge/trajectory-imports.json")
        assert meta.exists()
        records = __import__("json").loads(meta.read_text())
        assert records[-1]["thread_id"] == "proj-copy"


@pytest.mark.asyncio
async def test_trajectories_import_conflict_and_bad_schema(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _seed_thread("proj-existing")

        # schema inválido → 422
        r = await ac.post(
            "/api/v1/trajectories/import",
            json={
                "schema_version": "9.9",
                "thread_id": "x",
                "created_at": "2026-08-05T00:00:00Z",
                "steps": [],
                "events": [],
            },
        )
        assert r.status_code == 422

        # thread já existe → 409
        r2 = await ac.post(
            "/api/v1/trajectories/import",
            json={
                "schema_version": "1.0",
                "thread_id": "proj-existing",
                "created_at": "2026-08-05T00:00:00Z",
                "steps": [],
                "events": [],
            },
        )
        assert r2.status_code == 409

        # checkpoint inexistente → 404
        r3 = await ac.get("/api/v1/trajectories/proj-existing/checkpoints/nao-existe")
        assert r3.status_code == 404

        # export de thread inexistente → 404
        r4 = await ac.get("/api/v1/trajectories/thread-inexistente/export")
        assert r4.status_code == 404


@pytest.mark.asyncio
async def test_trajectories_fork(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await _seed_thread("proj-fork")

        r = await ac.post("/api/v1/trajectories/proj-fork/fork")
        assert r.status_code == 201
        data = r.json()
        assert data["source_thread_id"] == "proj-fork"
        assert data["fork_thread_id"].startswith("proj-fork-fork-")

        # fork de thread inexistente → 404
        r404 = await ac.post("/api/v1/trajectories/thread-inexistente/fork")
        assert r404.status_code == 404
