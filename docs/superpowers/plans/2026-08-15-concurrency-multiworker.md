# Concurrency multi-worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preparar o LoopForge para `uvicorn --workers N` (múltiplas instâncias): fila de runs global via Redis (pending + active com lease + params), semáforo `max_concurrent` global atômico, broadcast WS cross-worker, rate limit global, cancel remoto e `lf serve --workers`.

**Architecture:** `RunQueueState` in-memory vira interface com 2 backends (`memory` = atual, BC; `redis` = fila global). Promoção atômica via script Lua (`SCARD active < max → RPOP pending → ZADD active`). Worker loop por processo: pub/sub `lf:notify` acorda, tenta promoção, vencedor executa `_run_pipeline` localmente. Event bus: journal já é SQLite (ok cross-process); broadcast WS via pub/sub `lf:events` repassado ao ws_manager local. Rate limit: ZSET Redis global quando backend=redis. Cancel: pub/sub `lf:cancel` + registry local. `--workers` no CLI com validação.

**Tech Stack:** Python FastAPI + redis-py async + fakeredis (testes), docker-compose (serviço redis:7), uvicorn.

## Global Constraints

- Idioma: docs/comentários em PT, identificadores em EN.
- Backend: ruff `--select E,F,W,I,N,UP,SIM` (line-length 120, ignore E501/SIM117/E402/F401), mypy `src/lf`, pytest `tests/` (coverage ≥75%).
- Deps via `uv add` (atualiza `uv.lock` obrigatoriamente); CI usa `pip install -e .`.
- **BC obrigatória**: backend default `memory` — todos os testes existentes (107 arquivos) e o modo local single-process continuam funcionando SEM Redis.
- Envs novas: `LF_QUEUE_BACKEND` (`memory`|`redis`, default `memory`), `LF_REDIS_URL` (default `redis://localhost:6379`).
- `max_concurrent_runs` (schema.py:151, default 2) é **global** entre workers (semáforo no Redis), não por processo.
- Fila/active/params são processo-local hoje (`app.py:207-215`); crash recovery C9 (`app.py:80-101`) marca running/queued → failed no boot — continua cobrindo restart.
- Testes de fila atuais: `tests/test_run_queue.py` (fixture: chdir tmp_path, LF_API_TEST=1, LF_API_REQUIRE_AUTH=false, patch load_ade_config → max_concurrent_runs=1, init_db/close_db, AsyncClient ASGITransport, `_wait_status`) e `tests/test_parallel_runs.py` (default max 2, 3 POSTs → r3 queued).

---

### Task 1: Deps — `redis` + `fakeredis` (dev)

**Files:**
- Modify: `agentes/LoopForge/pyproject.toml` (via `uv add`)
- Modify: `agentes/LoopForge/uv.lock` (via `uv add`)

**Interfaces:**
- Produces: `redis` em `[project].dependencies`; `fakeredis` em `[project.optional-dependencies].dev`

- [ ] **Step 1: Adicionar deps**

Run (em `agentes/LoopForge`):
```bash
uv add redis && uv add --dev fakeredis
```

- [ ] **Step 2: Verificar**

Run: `grep -n "redis" pyproject.toml && python -c "import redis, fakeredis; print(redis.__version__)"`
Expected: redis em deps, fakeredis em dev; import OK (usar venv: `.venv/bin/python` se aplicável)

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(deps): redis + fakeredis (fila multi-worker)"
```

---

### Task 2: Config — `LF_QUEUE_BACKEND` + `LF_REDIS_URL` em APISettings

**Files:**
- Modify: `agentes/LoopForge/src/lf/api/config.py` (APISettings :57-84)
- Test: `agentes/LoopForge/tests/test_config_settings.py` (verificar existência; criar se não houver, padrão dos testes de config existentes)

**Interfaces:**
- Consumes: `APISettings` (config.py:57), `get_api_settings` (config.py:94)
- Produces: `queue_backend: str = "memory"` (env `LF_QUEUE_BACKEND`), `redis_url: str = "redis://localhost:6379"` (env `LF_REDIS_URL`)

- [ ] **Step 1: Teste que falha**

`tests/test_config_settings.py`:

```python
"""Config nova da fila multi-worker (envs LF_QUEUE_BACKEND / LF_REDIS_URL)."""

from lf.api.config import APISettings


def test_queue_backend_default_memory():
    settings = APISettings()
    assert settings.queue_backend == "memory"
    assert settings.redis_url == "redis://localhost:6379"


def test_queue_backend_env_override(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("LF_REDIS_URL", "redis://cache:6380")
    settings = APISettings()
    assert settings.queue_backend == "redis"
    assert settings.redis_url == "redis://cache:6380"
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_config_settings.py -x`
Expected: FAIL (atributos inexistentes)

- [ ] **Step 3: Implementar**

`config.py` — adicionar no `APISettings` (após `rate_limit_per_min` :80):

```python
    # Fila multi-worker (E3): "memory" = fila in-process (BC, single worker);
    # "redis" = fila global via Redis (pending/active/params + semáforo).
    queue_backend: str = "memory"
    redis_url: str = "redis://localhost:6379"
```

- [ ] **Step 4: Rodar p/ passar**

Run: `pytest tests/test_config_settings.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lf/api/config.py tests/test_config_settings.py
git commit -m "feat(api): settings LF_QUEUE_BACKEND/LF_REDIS_URL"
```

---

### Task 3: Backend — `src/lf/api/queue.py` (interface + MemoryQueue + RedisQueue)

**Files:**
- Create: `agentes/LoopForge/src/lf/api/queue.py`
- Test: `agentes/LoopForge/tests/test_queue_redis.py`

**Interfaces:**
- Produces (contrato da interface, consumido pelas Tasks 4-7):

```python
class RunQueue(Protocol):
    def enqueue(self, run_id: str, params: dict) -> None: ...
    async def try_promote(self, max_concurrent: int) -> list[tuple[str, dict]]: ...
    def release(self, run_id: str) -> None: ...
    def remove_pending(self, run_id: str) -> bool: ...
    def active_ids(self) -> set[str]: ...
    def pending_ids(self) -> list[str]: ...
    def params(self, run_id: str) -> dict | None: ...
    async def close(self) -> None: ...
    def lease_refresh(self, run_id: str) -> None: ...  # heartbeat (redis)
```

`create_queue(backend: str, redis_url: str, max_concurrent: int) -> RunQueue` — factory.

- [ ] **Step 1: Testes que falham**

`tests/test_queue_redis.py` (fakeredis `FakeAsyncRedis`; padrão async):

```python
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
    rq.enqueue("r1", {"idea": "a"})
    rq.enqueue("r2", {"idea": "b"})
    rq.enqueue("r3", {"idea": "c"})
    promoted = await rq.try_promote(2)
    assert {rid for rid, _ in promoted} == {"r1", "r2"}
    assert {rid for rid, _ in await rq.try_promote(2)} == set()  # cheio
    rq.release("r1")
    promoted = await rq.try_promote(2)
    assert {rid for rid, _ in promoted} == {"r3"}
    assert rq.params("r3") == {"idea": "c"}


@pytest.mark.asyncio
async def test_lease_expirado_volta_a_pending(rq):
    rq.enqueue("r1", {"idea": "a"})
    await rq.try_promote(2)
    assert "r1" in rq.active_ids()
    # simula lease expirado (score antigo) + próxima promoção reaproveita
    await rq.redis.zadd("lf:q:active", {"r1": 0.0})
    promoted = await rq.try_promote(2)
    assert "r1" in {rid for rid, _ in promoted}


@pytest.mark.asyncio
async def test_remove_pending_cancela_fila(rq):
    rq.enqueue("r1", {"idea": "a"})
    rq.enqueue("r2", {"idea": "b"})
    assert rq.remove_pending("r2") is True
    assert "r2" not in rq.pending_ids()
    assert rq.remove_pending("nao-existe") is False


@pytest.mark.asyncio
async def test_factory_memory_vs_redis():
    from lf.api.queue import MemoryQueue
    assert isinstance(create_queue("memory", "redis://x", 2), MemoryQueue)
    assert isinstance(create_queue("redis", "redis://x", 2), RedisQueue)
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_queue_redis.py -x`
Expected: FAIL (módulo não existe)

- [ ] **Step 3: Implementar `queue.py`**

```python
"""Fila de execução E3 com backends memory (BC) e redis (multi-worker).

Contrato comum (RunQueue) consumido por app.py — TODOS os métodos são
async (implementação uniforme; MemoryQueue usa corpos sync):
  enqueue → pendencia FIFO; try_promote → até max_concurrent (atômico no
  redis via Lua); release → libera slot; remove_pending → cancel de fila;
  params → dicionário de execução retido até a promoção.

Redis: pending LIST (RPUSH/LPOP), active ZSET (score = lease epoch),
params HASH com TTL. Promoção atômica em Lua: expira leases vencidos
(score < now - lease), conta ativos e promove enquanto couber.
"""

from __future__ import annotations

import time
from typing import Protocol

from redis.asyncio import Redis

# Chaves redis
_PENDING = "lf:q:pending"
_ACTIVE = "lf:q:active"
_PARAMS = "lf:q:params:{run_id}"

_PROMOTE_SCRIPT = """
local pending = KEYS[1]
local active = KEYS[2]
local max = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local lease = tonumber(ARGV[3])
-- expira leases vencidos (worker morto) → devolve a pending
local expired = redis.call('ZRANGEBYSCORE', active, '-inf', now - lease)
for _, rid in ipairs(expired) do
  redis.call('ZREM', active, rid)
  redis.call('RPUSH', pending, rid)
end
local promoted = {}
while redis.call('ZCARD', active) < max do
  local rid = redis.call('LPOP', pending)
  if not rid then break end
  redis.call('ZADD', active, now, rid)
  table.insert(promoted, rid)
end
return promoted
"""


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
        script = self.redis.register_script(_PROMOTE_SCRIPT)
        now = time.time()
        rids = await script(
            keys=[_PENDING, _ACTIVE],
            args=[max_concurrent, now, self.lease_seconds],
        )
        out: list[tuple[str, dict]] = []
        for rid in rids:
            params = await self.redis.hgetall(_PARAMS.format(run_id=rid))
            out.append((rid, {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in params.items()}))
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
        return {r.decode() if isinstance(r, bytes) else r for r in await self.redis.zrange(_ACTIVE, 0, -1)}

    async def pending_ids(self) -> list[str]:
        return [r.decode() if isinstance(r, bytes) else r for r in await self.redis.lrange(_PENDING, 0, -1)]

    async def params(self, run_id: str) -> dict | None:
        raw = await self.redis.hgetall(_PARAMS.format(run_id=run_id))
        if not raw:
            return None
        return {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}

    async def close(self) -> None:
        await self.redis.aclose()

    async def lease_refresh(self, run_id: str) -> None:
        await self.redis.zadd(_ACTIVE, {run_id: time.time()})


def create_queue(backend: str, redis_url: str, max_concurrent: int) -> RunQueue:
    """Factory: 'memory' (BC) ou 'redis' (multi-worker)."""
    if backend == "redis":
        return RedisQueue(redis=Redis.from_url(redis_url, decode_responses=False), max_concurrent=max_concurrent)
    return MemoryQueue(max_concurrent=max_concurrent)
```

Nota de coerência: a interface no módulo declara métodos sync (contrato de uso no app.py), mas RedisQueue os expõe async. **Decisão**: os métodos da interface são `async` em ambas as implementações (MemoryQueue ganha `async def` com os mesmos corpos sync). Ajuste os tipos do Protocol para `async` e faça MemoryQueue usar `async def` em todos (corpos idênticos). Os testes acima refletem o uso async (`await rq.try_promote(...)`). Ajustar enqueue/remove_pending/active_ids/pending_ids/params/lease_refresh/close para `async def` em ambas as classes e no Protocol.

- [ ] **Step 4: Rodar p/ passar**

Run: `pytest tests/test_queue_redis.py -x`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lf/api/queue.py tests/test_queue_redis.py
git commit -m "feat(queue): interface RunQueue + backends memory/redis (fila global)"
```

---

### Task 4: app.py — trocar RunQueueState por `create_queue` + worker loop

**Files:**
- Modify: `agentes/LoopForge/src/lf/api/app.py` (RunQueueState :104-119 → remover/substituir; create_app :207-215; `_execute_pipeline_in_background` :1145-1180; `_promote_next` :1094-1143; `_run_pipeline` finally; `_cancel_run_impl` :856; lifespan :63)
- Test: `agentes/LoopForge/tests/test_run_queue.py` + `tests/test_parallel_runs.py` (BC) + `tests/test_queue_redis_api.py` (novo, integração)

**Interfaces:**
- Consumes: `create_queue`, `RunQueue` (Task 3); `settings.queue_backend/redis_url` (Task 2)
- Produces: `app.state.run_queue: RunQueue`; `app.state.queue_worker: asyncio.Task | None` (loop de worker no backend redis); `app.state.queue_notify: pubsub` p/ `lf:notify`

- [ ] **Step 1: Teste que falha (integração redis)**

`tests/test_queue_redis_api.py` (fakeredis injectado via monkeypatch em `create_queue`; ou env `LF_QUEUE_BACKEND=redis` + monkeypatch do factory):

```python
"""Integração API × fila Redis (fakeredis): 3 runs, máx 2, 3ª queued.

Mesmo shape do test_parallel_runs.py, com backend redis.
"""

import pytest
import pytest_asyncio
from fakeredis import FakeAsyncRedis
from httpx import ASGITransport, AsyncClient

import lf.api.queue as queue_mod
from lf.api.app import create_app
from lf.api.config import APISettings
from lf.api.database import close_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_redis_queue_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    fake = FakeAsyncRedis()

    def _factory(backend: str, redis_url: str, max_concurrent: int):
        from lf.api.queue import RedisQueue
        return RedisQueue(redis=fake, max_concurrent=max_concurrent)

    monkeypatch.setattr(queue_mod, "create_queue", _factory)
    await init_db()
    yield fake
    await close_db()


@pytest.mark.asyncio
async def test_tres_runs_max_2_terceira_queued():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ids = []
        for i in range(3):
            r = await ac.post("/api/v1/runs", json={"idea": f"r{i}", "stack": "python", "mock_llm": True})
            assert r.status_code == 201, r.text
            ids.append(r.json()["id"])
        # Poll até a 3ª nascer queued (as 2 primeiras completam rápido com mock)
        for _ in range(50):
            r = await ac.get(f"/api/v1/runs/{ids[2]}")
            if r.json()["status"] != "queued":
                await asyncio.sleep(0.05)
            else:
                break
        statuses = []
        for rid in ids:
            r = await ac.get(f"/api/v1/runs/{rid}")
            statuses.append(r.json()["status"])
        assert "running" in statuses or "completed" in statuses
```

(Importar `asyncio`; o padrão de poll pode seguir `_wait_status` de test_run_queue.py:39.)

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_queue_redis_api.py -x`
Expected: FAIL (RunQueueState não usa redis)

- [ ] **Step 3: Implementar**

`app.py` — importar `create_queue` de `lf.api.queue`; substituir a classe `RunQueueState` por um alias (BC para código existente que a use — verificar usos; se nenhum externo, remover) e trocar a criação em `create_app` (:207-215):

```python
    # Estado da fila E3 (M-21) — N runs ativas + fila FIFO. Backend por env:
    # memory (BC, single-process) ou redis (multi-worker global).
    from lf.config.loader import load_ade_config
    from lf.api.queue import create_queue

    max_concurrent = load_ade_config().runner.max_concurrent_runs
    app.state.run_queue = create_queue(
        backend=settings.queue_backend,
        redis_url=settings.redis_url,
        max_concurrent=max_concurrent,
    )
    app.state.run_tasks = {}  # dict[str, asyncio.Task] — local do processo
    app.state.queue_worker = None  # task do worker loop (redis)
```

`_execute_pipeline_in_background` (:1145-1180) — trocar o corpo para o contrato async (idempotência já dentro de cada backend: MemoryQueue checa active/pending; RedisQueue checa ZSCORE/LPOS):

```python
    q = app.state.run_queue
    await q.enqueue(run_id, {
        "idea": idea,
        "stack": stack,
        "mock_llm": mock_llm,
        "routing_mode": routing_mode,
        "interactive": interactive,
        "model": model,
        "pipeline_snapshot": pipeline_snapshot,
        "resume": resume,
    })
    await _promote_next(app)
    # redis: acordar worker loop (outros workers também tentam promoção)
    if getattr(app.state, "queue_notify", None):
        await app.state.queue_notify.publish("lf:notify", run_id)
```

`_promote_next` (:1094-1143) — para redis, o worker loop chama `try_promote` e executa as runs promovidas localmente; para memory, manter o loop atual. Estrutura sugerida:

```python
async def _promote_next(app: FastAPI) -> None:
    """Promove runs enfileiradas (FIFO) enquanto houver vaga.

    memory: promoção direta + execução local (BC).
    redis: promoção global atômica; runs promovidas executam NESTE worker
    (asyncio.create_task local) — o registro run_tasks é por processo.
    """
    q = app.state.run_queue
    promoted = await q.try_promote(q.max_concurrent)
    for run_id, params in promoted:
        idea = params.get("idea", "")
        stack = params.get("stack", "python")
        mock_llm = params.get("mock_llm", False)
        routing_mode = params.get("routing_mode", "full")
        interactive = params.get("interactive", False)
        model = params.get("model")
        pipeline_snapshot = params.get("pipeline_snapshot")
        resume = params.get("resume", False)
        await _set_run_status(run_id, "running", thread_id=f"run-{run_id}", parent_run_id=run_id)
        task = asyncio.create_task(
            _run_pipeline(app, run_id=run_id, idea=idea, stack=stack, mock_llm=mock_llm,
                          routing_mode=routing_mode, interactive=interactive, model=model,
                          pipeline_snapshot=pipeline_snapshot, resume=resume)
        )
        app.state.run_tasks[run_id] = task
        task.add_done_callback(lambda t, rid=run_id: app.state.run_tasks.pop(rid, None))
        # Heartbeat do lease (redis): renova enquanto a run executa — sem isso
        # uma run longa (> lease) perderia o lease e outro worker re-promoveria
        # (execução duplicada). Cancela junto com o fim da task.
        if not isinstance(q, MemoryQueue):
            keeper = asyncio.create_task(_lease_heartbeat(q, run_id))
            task.add_done_callback(lambda _t, k=keeper: k.cancel())
```

E definir o helper (perto de `_promote_next`):

```python
async def _lease_heartbeat(q, run_id: str) -> None:
    """Renova o lease da run ativa a cada ~1/3 do lease (worker vivo)."""
    try:
        interval = max(5.0, getattr(q, "lease_seconds", 60) / 3)
        while True:
            await asyncio.sleep(interval)
            await q.lease_refresh(run_id)
    except asyncio.CancelledError:
        pass
```
```

`_run_pipeline` finally — onde hoje chama `_promote_next` e libera slot (localizar no final da função): trocar `q.active.discard(run_id)` por `await q.release(run_id)` + `await _promote_next(app)` + (redis) notificar worker loop. Como o finally de `_run_pipeline` é onde a run termina, o `release` + `try_promote` subsequente podem rodar no próprio finally (sem depender do worker loop) — o loop é o gatilho inicial/paralelo.

Worker loop (lifespan, :63): quando `settings.queue_backend == "redis"`, criar task:

```python
async def _queue_worker_loop(app: FastAPI) -> None:
    """Loop de worker (redis): escuta lf:notify e promove runs globais."""
    import redis.asyncio as aioredis

    q = app.state.run_queue
    pubsub = q.redis.pubsub()
    await pubsub.subscribe("lf:notify")
    app.state.queue_notify = pubsub
    try:
        while True:
            # aguarda notificação ou timeout p/ tentar promoção (crash leave)
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is not None:
                await _promote_next(app)
            elif await q.active_ids() or await q.pending_ids():
                # tenta reaproveitar slots/leases expirados periodicamente
                await _promote_next(app)
    finally:
        await pubsub.unsubscribe("lf:notify")
```

Registrar no lifespan: `app.state.queue_worker = asyncio.create_task(_queue_worker_loop(app))` (com cancelamento no shutdown). Importar `MemoryQueue` de `lf.api.queue` para o isinstance.

`_cancel_run_impl` (:856) — trocar manipulação direta de `q.pending/q.active` por `remove_pending`/`release` (ambos async no contrato):

```python
    removed = await q.remove_pending(run_id)
    await q.release(run_id)
```

(Manter a semântica atual: cancel remove de pending preservando ordem + descarta active; task local cancelada via run_tasks — ver código atual :856-895 e adaptar.)

- [ ] **Step 4: Rodar testes p/ passar**

Run: `pytest tests/test_run_queue.py tests/test_parallel_runs.py tests/test_queue_redis_api.py`
Expected: PASS (BC memory intocado; integração redis passa)

- [ ] **Step 5: Commit**

```bash
git add src/lf/api/app.py tests/test_queue_redis_api.py
git commit -m "feat(api): fila por backend (memory/redis) + worker loop global"
```

---

### Task 5: Event bus cross-worker (pub/sub lf:events → ws local) + rate limit redis

**Files:**
- Modify: `agentes/LoopForge/src/lf/api/events.py` (EventBus :118; `_broadcast` :164; `publish` :182)
- Modify: `agentes/LoopForge/src/lf/api/rate_limit.py` (RateLimitMiddleware :14-87)
- Test: `agentes/LoopForge/tests/test_events_redis.py` + `tests/test_rate_limit_redis.py`

**Interfaces:**
- Consumes: `ws_manager.broadcast/send_to_run` (websocket_manager.py:64/83), `app.state.queue_backend`
- Produces: EventBus com publicador redis opcional (canal `lf:events`); RateLimitMiddleware com backend redis opcional (ZSET `lf:rl:{key}`)

- [ ] **Step 1: Testes que falham**

`tests/test_events_redis.py`:

```python
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
        await bus.publish("run-1", "run_created", {"idea": "x"})
        pubsub = fake.pubsub()
        await pubsub.subscribe("lf:events")
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
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
```

`tests/test_rate_limit_redis.py`:

```python
"""Rate limit global via Redis (ZSET) quando configurado; in-memory sem."""

import asyncio

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
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_events_redis.py tests/test_rate_limit_redis.py -x`
Expected: FAIL (métodos inexistentes)

- [ ] **Step 3: Implementar**

`events.py` — EventBus ganha redis opcional (singleton `event_bus` :304 permanece; `configure_redis` chamado no create_app quando backend=redis):

```python
    # no __init__:
    self._redis = None  # Redis | None — publicador de lf:events

    def configure_redis(self, redis: Redis) -> None:
        """Ativa publicador redis (canal lf:events) — multi-worker WS."""
        self._redis = redis
```

No `publish` (:182), após persistir o journal e antes/depois do `_broadcast` local:

```python
        if self._redis is not None:
            try:
                await self._redis.publish("lf:events", json.dumps(envelope))
            except Exception:
                logger.warning("Falha ao publicar evento no redis", exc_info=True)
```

(Importar `redis.asyncio.Redis` apenas p/ type hint com `TYPE_CHECKING`; usar `from redis.asyncio import Redis` com try/except import opcional para não quebrar sem dep.)

`app.py` — no lifespan (backend=redis): `event_bus.configure_redis(q.redis)` + task que subscreve `lf:events` e repassa ao ws_manager local:

```python
async def _events_forwarder(app: FastAPI) -> None:
    q = app.state.run_queue
    pubsub = q.redis.pubsub()
    await pubsub.subscribe("lf:events")
    try:
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is None:
                continue
            try:
                data = json.loads(msg["data"])
            except Exception:
                continue
            run_id = data.get("run_id")
            if run_id:
                await ws_manager.send_to_run(run_id, data)
            await ws_manager.broadcast(data)
    finally:
        await pubsub.unsubscribe("lf:events")
```

(Importar `event_bus` de `lf.api.events` e `ws_manager` de `lf.api.websocket_manager`.)

`rate_limit.py` — RateLimitMiddleware aceita `redis=None`:

```python
    def __init__(self, app, limit_per_min: int = 300, window_seconds: int = 60, redis=None) -> None:
        self.app = app
        self.limit = limit_per_min
        self.window = window_seconds
        self.redis = redis  # Redis | None — None = in-memory (BC)
        self._hits: dict[str, list[float]] = {}
        self._prune_threshold = 10_000
```

`_check_window` — se `self.redis` setado, usar ZSET:

```python
    async def _check_window(self, key: str, now: float) -> tuple[bool, int]:
        if self.redis is not None:
            rkey = f"lf:rl:{key}"
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(rkey, "-inf", now - self.window)
            pipe.zcard(rkey)
            pipe.zadd(rkey, {str(now): now})
            pipe.expire(rkey, self.window * 2)
            _, count, _, _ = await pipe.execute()
            if int(count) >= self.limit:
                return False, 1
            return True, 0
        # caminho in-memory atual (inalterado)
        ...
```

Ajustar `__call__` (:64-87) para `await self._check_window(...)` (era sync) e o teste unitário correspondente (o teste acima chama `_check_window` com `await`? — nos testes escrevi chamadas sync; alinhar: tornar `_check_window` async e usar `await` nos testes; o `__call__` já é async). Rever os snippets de teste para `await mw._check_window(...)`.

`app.py` middleware (:242) — passar redis quando backend=redis:

```python
    if settings.rate_limit_per_min > 0:
        if settings.queue_backend == "redis":
            app.add_middleware(RateLimitMiddleware, limit_per_min=settings.rate_limit_per_min, redis=app.state.run_queue.redis)
        else:
            app.add_middleware(RateLimitMiddleware, limit_per_min=settings.rate_limit_per_min)
```

- [ ] **Step 4: Rodar p/ passar**

Run: `pytest tests/test_events_redis.py tests/test_rate_limit_redis.py && pytest tests/ -q`
Expected: PASS (BC preservado)

- [ ] **Step 5: Commit**

```bash
git add src/lf/api/events.py src/lf/api/rate_limit.py src/lf/api/app.py tests/test_events_redis.py tests/test_rate_limit_redis.py
git commit -m "feat(api): broadcast WS e rate limit cross-worker via redis"
```

---

### Task 6: Cancel remoto + `lf serve --workers` + docker-compose redis

**Files:**
- Modify: `agentes/LoopForge/src/lf/cli/commands/serve.py`
- Modify: `agentes/LoopForge/docker-compose.yml`
- Modify: `agentes/LoopForge/src/lf/api/app.py` (cancel cross-worker: `_cancel_run_impl` :856 + worker loop escuta `lf:cancel`)
- Test: `agentes/LoopForge/tests/test_serve_workers.py`

**Interfaces:**
- Consumes: `_cancel_run_impl` (app.py:856), `app.state.run_tasks`, `serve_cmd` (serve.py:17)
- Produces: `--workers N` no `lf serve` (valida: workers>1 exige `LF_QUEUE_BACKEND=redis`; reload×workers inválido); serviço `redis:7` no compose + `LF_REDIS_URL`; cancel cross-worker via canal `lf:cancel`

- [ ] **Step 1: Teste que falha**

`tests/test_serve_workers.py`:

```python
"""Validação de --workers no lf serve (multi-processo exige fila redis)."""

import pytest
from click.testing import CliRunner

from lf.cli.commands.serve import serve_cmd


def test_workers_1_ok_sem_redis(monkeypatch):
    monkeypatch.delenv("LF_QUEUE_BACKEND", raising=False)
    runner = CliRunner()
    # intercepta uvicorn.run p/ não subir servidor de verdade
    import lf.cli.commands.serve as serve_mod

    captured = {}

    def fake_uvicorn(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(serve_mod.uvicorn, "run", fake_uvicorn)
    result = runner.invoke(serve_cmd, ["--workers", "1", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert captured.get("workers") == 1


def test_workers_2_sem_redis_erro(monkeypatch):
    monkeypatch.delenv("LF_QUEUE_BACKEND", raising=False)
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--port", "8123"])
    assert result.exit_code != 0
    assert "LF_QUEUE_BACKEND=redis" in result.output


def test_workers_2_com_redis_ok(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    import lf.cli.commands.serve as serve_mod

    captured = {}

    def fake_uvicorn(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(serve_mod.uvicorn, "run", fake_uvicorn)
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert captured.get("workers") == 2


def test_reload_com_workers_erro(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--reload", "--port", "8123"])
    assert result.exit_code != 0
    assert "reload" in result.output.lower()
```

- [ ] **Step 2: Rodar p/ ver falhar**

Run: `pytest tests/test_serve_workers.py -x`
Expected: FAIL (sem --workers)

- [ ] **Step 3: Implementar**

`serve.py` — adicionar opção e validação:

```python
@click.command(name="serve")
@click.option("--host", default="127.0.0.1", help="Endereço de host (padrão: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Porta HTTP (padrão: 8000)")
@click.option("--reload", is_flag=True, help="Ativa modo auto-reload para desenvolvimento")
@click.option("--no-ui", is_flag=True, help="Não serve dashboard/SPA, apenas a API")
@click.option("--workers", default=1, type=int, help="Número de workers (multi-processo exige LF_QUEUE_BACKEND=redis)")
def serve_cmd(host: str, port: int, reload: bool, no_ui: bool, workers: int):
    """Inicia o servidor de API REST, WebSockets e Web Dashboard do LoopForge v6."""
    if workers > 1 and os.environ.get("LF_QUEUE_BACKEND") != "redis":
        raise click.ClickException(
            "--workers > 1 exige LF_QUEUE_BACKEND=redis (fila/eventos/rate-limit globais)."
        )
    if reload and workers > 1:
        raise click.ClickException("--reload é incompatível com --workers > 1.")
    ...
    uvicorn.run(
        "lf.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        workers=workers,
    )
```

`docker-compose.yml` — adicionar serviço redis + env no app:

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: loopforge_redis
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data

  loopforge:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: loopforge_engine
    depends_on:
      - redis
    ports:
      - "8000:8000"
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
      - OPENROUTER_MODEL=${OPENROUTER_MODEL:-inclusionai/ling-3.0-flash:free}
      - LF_API_HOST=0.0.0.0
      - LF_API_PORT=8000
      - LF_QUEUE_BACKEND=${LF_QUEUE_BACKEND:-memory}
      - LF_REDIS_URL=${LF_REDIS_URL:-redis://redis:6379}
    volumes:
      - loopforge_data:/app/.loopforge
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 3

volumes:
  loopforge_data:
    driver: local
  redis_data:
    driver: local
```

`app.py` — cancel cross-worker: no `_cancel_run_impl`, após remover de pending/active e cancelar task local, publicar no canal `lf:cancel` (workers remotos cancelam a task local via run_tasks):

```python
    # C8 multi-worker: task roda no worker que promoveu. Publica lf:cancel —
    # cada worker cancela a task local se tiver no run_tasks.
    if isinstance(q, RedisQueue):
        await q.redis.publish("lf:cancel", run_id)
```

E no worker loop (Task 4), adicionar assinatura `lf:cancel` → handler:

```python
    async def _on_cancel(rid: str) -> None:
        task = app.state.run_tasks.get(rid)
        if task is not None:
            task.cancel()
```

(Registrar no loop: ao receber mensagem do canal lf:cancel — pode ser o mesmo `_queue_worker_loop` com subscribe múltiplo, ou task separada `_cancel_listener`. Simplicidade: segunda task `_cancel_listener` com pubsub próprio em `lf:cancel`.)

- [ ] **Step 4: Rodar p/ passar**

Run: `pytest tests/test_serve_workers.py && pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lf/cli/commands/serve.py docker-compose.yml src/lf/api/app.py tests/test_serve_workers.py
git commit -m "feat(cli): --workers com validação + redis no compose + cancel remoto"
```

---

### Task 7: `.env.example` + docs + validação final

**Files:**
- Modify: `agentes/LoopForge/.env.example`
- Modify: `agentes/LoopForge/README.md` (seção operação multi-worker, se houver; senão docs/configuration.md)

**Interfaces:**
- Consumes: envs novas (Task 2)

- [ ] **Step 1: Documentar envs**

`.env.example` — adicionar:

```bash
# ─── Multi-worker (fila global) ──────────────────────────────────────────
# LF_QUEUE_BACKEND=memory   # memory (single-process, BC) | redis (multi-worker)
# LF_REDIS_URL=redis://localhost:6379
```

`docs/configuration.md` (ou README) — seção curta: fila redis p/ `--workers > 1`, `lf serve --workers N`, `docker compose up -d` sobe redis.

- [ ] **Step 2: Validação final engine**

Run (em `agentes/LoopForge`): `ruff check --select E,F,W,I,N,UP,SIM src/lf tests && mypy src/lf && pytest --cov=src/lf --cov-fail-under=75 tests/`
Expected: PASS

- [ ] **Step 3: Smoke manual**

Run: `docker compose up -d redis` → `LF_QUEUE_BACKEND=redis lf serve --workers 2 --port 8000` → 3 runs via API: máx 2 ativas global; `GET /runs/queue` reflete fila global; cancel de uma run queued remove da fila; WS recebe eventos (worker A executa, worker B entrega WS).
Se sem docker: `redis-server` local ou pular smoke (testes fakeredis cobrem).

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md docs/configuration.md
git commit -m "docs: envs multi-worker e operação com redis"
```
