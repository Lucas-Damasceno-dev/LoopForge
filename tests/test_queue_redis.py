"""Fila Redis (fakeredis): promoção global, lease, cancel e params.

Sem infra real — fakeredis emula o protocolo; os testes da API (Task 6)
cobrem integração com create_app.
"""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis

from lf.api.queue import RedisQueue, create_queue


@pytest_asyncio.fixture
async def rq():
    redis = FakeAsyncRedis()
    queue = RedisQueue(redis=redis, max_concurrent=2, lease_seconds=60)
    yield queue
    await queue.close()


@pytest.mark.asyncio
async def test_enqueue_promove_fifo_ate_max_concurrent(rq):
    await rq.enqueue("r1", {"idea": "a"})
    await rq.enqueue("r2", {"idea": "b"})
    await rq.enqueue("r3", {"idea": "c"})
    promoted = await rq.try_promote(2)
    assert {rid for rid, _ in promoted} == {"r1", "r2"}
    assert {rid for rid, _ in await rq.try_promote(2)} == set()  # cheio
    await rq.release("r1")
    promoted = await rq.try_promote(2)
    assert {rid for rid, _ in promoted} == {"r3"}
    assert await rq.get_params("r3") == {"idea": "c"}


@pytest.mark.asyncio
async def test_lease_expirado_volta_a_pending(rq):
    await rq.enqueue("r1", {"idea": "a"})
    await rq.try_promote(2)
    assert "r1" in await rq.active_ids()
    # simula lease expirado (score antigo) + próxima promoção reaproveita
    await rq.redis.zadd("lf:q:active", {"r1": 0.0})
    promoted = await rq.try_promote(2)
    assert "r1" in {rid for rid, _ in promoted}


@pytest.mark.asyncio
async def test_remove_pending_cancela_fila(rq):
    await rq.enqueue("r1", {"idea": "a"})
    await rq.enqueue("r2", {"idea": "b"})
    assert await rq.remove_pending("r2") is True
    assert "r2" not in await rq.pending_ids()
    assert await rq.remove_pending("nao-existe") is False


@pytest.mark.asyncio
async def test_factory_memory_vs_redis():
    from lf.api.queue import MemoryQueue

    assert isinstance(create_queue("memory", "redis://x", 2), MemoryQueue)
    assert isinstance(create_queue("redis", "redis://x", 2), RedisQueue)
