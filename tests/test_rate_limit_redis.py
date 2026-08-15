"""Rate limit global via Redis (ZSET) quando configurado; in-memory sem."""

import pytest
from fakeredis import FakeAsyncRedis

from lf.api.rate_limit import RateLimitMiddleware


@pytest.mark.asyncio
async def test_rate_limit_redis_janela_global():
    fake = FakeAsyncRedis()
    mw = RateLimitMiddleware(app=None, limit_per_min=2, window_seconds=60, redis=fake)
    ok1, _ = await mw._check_window("key:teste", 1000.0)
    ok2, _ = await mw._check_window("key:teste", 1001.0)
    ok3, _ = await mw._check_window("key:teste", 1002.0)
    assert ok1 and ok2
    assert not ok3


@pytest.mark.asyncio
async def test_rate_limit_memory_sem_redis():
    mw = RateLimitMiddleware(app=None, limit_per_min=2, window_seconds=60)
    ok1, _ = await mw._check_window("key:teste", 1.0)
    ok2, _ = await mw._check_window("key:teste", 2.0)
    ok3, _ = await mw._check_window("key:teste", 3.0)
    assert ok1 and ok2
    assert not ok3
