"""Broadcast WS cross-worker: publish persiste no journal (SQLite) e
publica no canal lf:events (fakeredis)."""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

from lf.api.events import EventBus


@pytest.mark.asyncio
async def test_publish_publica_redis_quando_configurado(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    from lf.api.database import close_db, init_db

    await init_db()
    try:
        fake = FakeAsyncRedis()
        bus = EventBus()
        bus.configure_redis(fake)
        # Subscribe ANTES do publish: mensagens publicadas sem subscriber são
        # descartadas (semântica do Redis) — ordem corrigida vs snippet do brief.
        pubsub = fake.pubsub()
        await pubsub.subscribe("lf:events")
        await bus.publish("run-1", "run_created", {"idea": "x"})
        # Poll: no fakeredis a 1ª get_message drena o ack do subscribe e a
        # mensagem chega na iteração seguinte.
        msg = None
        for _ in range(5):
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is not None:
                break
        assert msg is not None and msg["type"] == "message"
        # journal persiste
        events = await bus.list_events("run-1")
        assert len(events) == 1
    finally:
        await close_db()


@pytest.mark.asyncio
async def test_publish_sem_redis_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    from lf.api.database import close_db, init_db

    await init_db()
    try:
        bus = EventBus()
        await bus.publish("run-1", "run_updated", {"status": "running"})
        events = await bus.list_events("run-1")
        assert len(events) == 1
    finally:
        await close_db()
