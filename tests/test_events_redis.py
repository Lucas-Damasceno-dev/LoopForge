"""Broadcast WS cross-worker: publish persiste no journal (SQLite) e
publica no canal lf:events (fakeredis)."""

import asyncio
import contextlib
import json

import pytest
from fakeredis import FakeAsyncRedis

from lf.api.app import _events_forwarder, create_app
from lf.api.events import WORKER_ID, EventBus, event_bus
from lf.api.queue import RedisQueue
from lf.api.websocket_manager import ws_manager


class FakeWS:
    """WebSocket falso p/ ws_manager: captura mensagens send_json."""

    def __init__(self):
        self.messages = []

    async def accept(self):
        pass

    async def send_json(self, message):
        self.messages.append(message)


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


@pytest.mark.asyncio
async def test_canal_lf_events_carrega_origin_do_worker(tmp_path, monkeypatch):
    """O envelope do CANAL (não o do journal/ws local) carrega origin=worker_id."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    fake = FakeAsyncRedis()
    bus = EventBus()
    bus.configure_redis(fake)
    pubsub = fake.pubsub()
    await pubsub.subscribe("lf:events")
    await bus.publish("run-1", "run_created", {"idea": "x"})
    msg = None
    for _ in range(5):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if msg is not None:
            break
    assert msg is not None
    data = json.loads(msg["data"])
    assert data.get("origin") == WORKER_ID
    assert data.get("event") == "run_created"  # envelope padrão preservado


@pytest.mark.asyncio
async def test_forwarder_nao_rebroadcasta_evento_local(tmp_path, monkeypatch):
    """Evento local NÃO chega 2× ao ws: publish broadcasta local + canal; o
    forwarder do MESMO worker pula a própria mensagem (dedup por worker-id)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    from lf.api.database import close_db

    await close_db()  # zera session_factory → publish usa fallback mem (sem DB)
    fake = FakeAsyncRedis()
    app = create_app()
    app.state.run_queue = RedisQueue(redis=fake, max_concurrent=2)
    event_bus.configure_redis(fake)
    ws = FakeWS()
    await ws_manager.connect("run-1", ws)
    pubsub = fake.pubsub()
    await pubsub.subscribe("lf:events")
    forwarder = asyncio.create_task(_events_forwarder(app))
    try:
        await event_bus.publish("run-1", "run_created", {"idea": "x"})
        for _ in range(10):
            await asyncio.sleep(0.05)
            if len(ws.messages) > 1:
                break
        assert len(ws.messages) == 1  # send_to_run local (1×), canal skipado
    finally:
        forwarder.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await forwarder
        event_bus.configure_redis(None)
        ws_manager.disconnect("run-1", ws)
        await close_db()
