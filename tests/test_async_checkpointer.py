from pathlib import Path

import pytest

from lf.pipeline.checkpointer import create_async_checkpointer


def _wal_mode(db_path: Path) -> str:
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_async_checkpointer_opens_with_wal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = Path(".loopforge/trajectories.db")
    saver = create_async_checkpointer(db)
    assert db.exists()
    assert _wal_mode(db) == "wal"
    await saver.setup()
    await saver.conn.close()


@pytest.mark.asyncio
async def test_async_checkpointer_roundtrip_put_get(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    await saver.setup()
    config = {
        "configurable": {
            "thread_id": "proj-t1",
            "checkpoint_ns": "",
            "checkpoint_id": None,
        }
    }
    checkpoint = {
        "id": "1ef-ade-fase1-0001",
        "v": 1,
        "ts": "2026-08-05T00:00:00Z",
        "channel_values": {"next_agent": "cpo"},
    }
    metadata = {"source": "loop", "step": 1}
    saved = await saver.aput(config, checkpoint, metadata, {})
    listed = []
    async for item in saver.alist(config, limit=10):
        listed.append(item)
    assert any(item.config["configurable"]["thread_id"] == "proj-t1" for item in listed)
    await saver.conn.close()
