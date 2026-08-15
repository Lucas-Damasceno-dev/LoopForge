"""Fila de execução E3 com backends memory (BC) e redis (multi-worker).

Contrato comum (RunQueue) consumido por app.py — TODOS os métodos são
async (implementação uniforme; MemoryQueue usa corpos sync):
  enqueue → pendencia FIFO; try_promote → até max_concurrent (atômico no
  redis via transação otimista WATCH/MULTI); release → libera slot;
  remove_pending → cancel de fila; params → dicionário de execução retido
  até a promoção.

Redis: pending LIST (RPUSH/LPOP), active ZSET (score = lease epoch),
params HASH com TTL. try_promote expira leases vencidos (score < now -
lease), devolve-os ao fim da pending e promove enquanto couber — tudo numa
transação WATCH/MULTI com retry em WatchError (equivalente ao script Lua
planejado; fakeredis não executa EVAL, então a lógica é implementada em
Python com atomicidade otimista).
"""

from __future__ import annotations

import asyncio
import time
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import WatchError

# Chaves redis
_PENDING = "lf:q:pending"
_ACTIVE = "lf:q:active"
_PARAMS = "lf:q:params:{run_id}"


def _decode(value: str | bytes) -> str:
    return value.decode() if isinstance(value, bytes) else value


class RunQueue(Protocol):
    """Contrato da fila de execução (memory | redis). Todos os métodos async."""

    async def enqueue(self, run_id: str, params: dict) -> None: ...
    async def try_promote(self, max_concurrent: int) -> list[tuple[str, dict]]: ...
    async def release(self, run_id: str) -> None: ...
    async def remove_pending(self, run_id: str) -> bool: ...
    async def active_ids(self) -> set[str]: ...
    async def pending_ids(self) -> list[str]: ...
    async def params(self, run_id: str) -> dict | None: ...
    async def close(self) -> None: ...
    async def lease_refresh(self, run_id: str) -> None: ...


class MemoryQueue:
    """Backend in-process (BC): deque + set + dict — o RunQueueState atual."""

    def __init__(self, max_concurrent: int = 1) -> None:
        self.max_concurrent = max_concurrent
        self._pending: list[str] = []
        self._active: set[str] = set()
        self._params: dict[str, dict] = {}

    async def enqueue(self, run_id: str, params: dict) -> None:
        if run_id in self._active or run_id in self._pending:
            return
        self._params[run_id] = params
        self._pending.append(run_id)

    async def try_promote(self, max_concurrent: int) -> list[tuple[str, dict]]:
        promoted: list[tuple[str, dict]] = []
        while len(self._active) < max_concurrent and self._pending:
            run_id = self._pending.pop(0)
            self._active.add(run_id)
            promoted.append((run_id, self._params.pop(run_id, {})))
        return promoted

    async def release(self, run_id: str) -> None:
        self._active.discard(run_id)

    async def remove_pending(self, run_id: str) -> bool:
        if run_id in self._pending:
            self._pending.remove(run_id)
            self._params.pop(run_id, None)
            return True
        return False

    async def active_ids(self) -> set[str]:
        return set(self._active)

    async def pending_ids(self) -> list[str]:
        return list(self._pending)

    async def params(self, run_id: str) -> dict | None:
        return self._params.get(run_id)

    async def close(self) -> None:
        pass

    async def lease_refresh(self, run_id: str) -> None:
        pass


class RedisQueue:
    """Backend Redis: fila global entre workers (multi-processo).

    max_concurrent é o limite GLOBAL; lease (default 60s) é renovado pelo
    executor (heartbeat) e expira só com worker morto — a run volta a
    pending e outro worker promove (crash recovery C9 cobre o resto).
    """

    LEASE_DEFAULT = 60

    def __init__(self, redis: Redis, max_concurrent: int = 2, lease_seconds: int = LEASE_DEFAULT) -> None:
        self.redis = redis
        self.max_concurrent = max_concurrent
        self.lease_seconds = lease_seconds

    async def enqueue(self, run_id: str, params: dict) -> None:
        # Idempotente: já ativa (ZSCORE) ou já na fila (LPOS) → no-op.
        if await self.redis.zscore(_ACTIVE, run_id) is not None:
            return
        if await self.redis.lpos(_PENDING, run_id) is not None:
            return
        pipe = self.redis.pipeline()
        pipe.hset(_PARAMS.format(run_id=run_id), mapping=params)
        pipe.expire(_PARAMS.format(run_id=run_id), 86400)  # TTL 24h
        pipe.rpush(_PENDING, run_id)
        await pipe.execute()

    async def try_promote(self, max_concurrent: int) -> list[tuple[str, dict]]:
        """Expira leases vencidos e promove até max_concurrent (atômico).

        Transação otimista WATCH/MULTI: lê active/pending, computa em
        Python, executa mutações no MULTI; WatchError → retry (outro
        worker mexeu nas chaves).
        """
        now = time.time()
        lease_exp = now - self.lease_seconds
        promoted_ids: list[str] = []
        while True:
            try:
                async with self.redis.pipeline(transaction=True) as pipe:
                    await pipe.watch(_ACTIVE, _PENDING)
                    expired = [_decode(r) for r in await pipe.zrangebyscore(_ACTIVE, "-inf", lease_exp)]
                    active_count = await pipe.zcard(_ACTIVE)
                    pending = [_decode(r) for r in await pipe.lrange(_PENDING, 0, -1)]
                    slots = max_concurrent - (active_count - len(expired))
                    queue = list(pending) + expired
                    promoted_ids = queue[: max(slots, 0)]
                    pipe.multi()
                    for rid in expired:
                        pipe.zrem(_ACTIVE, rid)
                        pipe.rpush(_PENDING, rid)
                    for rid in promoted_ids:
                        pipe.lrem(_PENDING, 1, rid)
                        pipe.zadd(_ACTIVE, {rid: now})
                    await pipe.execute()
                    break
            except WatchError:
                await asyncio.sleep(0.01)
        out: list[tuple[str, dict]] = []
        for rid in promoted_ids:
            params = await self.redis.hgetall(_PARAMS.format(run_id=rid))
            out.append(
                (
                    rid,
                    {_decode(k): v.decode() if isinstance(v, bytes) else v for k, v in params.items()},
                )
            )
        return out

    async def release(self, run_id: str) -> None:
        await self.redis.zrem(_ACTIVE, run_id)

    async def remove_pending(self, run_id: str) -> bool:
        removed = await self.redis.lrem(_PENDING, 0, run_id)
        if removed:
            await self.redis.delete(_PARAMS.format(run_id=run_id))
            return True
        return False

    async def active_ids(self) -> set[str]:
        return {_decode(r) for r in await self.redis.zrange(_ACTIVE, 0, -1)}

    async def pending_ids(self) -> list[str]:
        return [_decode(r) for r in await self.redis.lrange(_PENDING, 0, -1)]

    async def params(self, run_id: str) -> dict | None:
        raw = await self.redis.hgetall(_PARAMS.format(run_id=run_id))
        if not raw:
            return None
        return {_decode(k): v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}

    async def close(self) -> None:
        await self.redis.aclose()

    async def lease_refresh(self, run_id: str) -> None:
        await self.redis.zadd(_ACTIVE, {run_id: time.time()})


def create_queue(backend: str, redis_url: str, max_concurrent: int) -> RunQueue:
    """Factory: 'memory' (BC) ou 'redis' (multi-worker)."""
    if backend == "redis":
        return RedisQueue(redis=Redis.from_url(redis_url, decode_responses=False), max_concurrent=max_concurrent)
    return MemoryQueue(max_concurrent=max_concurrent)
