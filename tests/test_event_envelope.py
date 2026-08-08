"""Testes do EventBus (Fase A, A3/M-05): envelope v1, journal persistido e seq por run.

Contrato (03-contratos-api.md §6, ADR-0002): cada evento publicado casa com o
envelope v1 ``{seq, event, run_id, timestamp, payload}`` e está persistido no
journal (tabela ``events`` em telemetry.sqlite — LF_API_TEST=1 → test_api.sqlite).
"""

import contextlib
import os

import pytest
import pytest_asyncio

from lf.api.database import close_db, init_db
from lf.api.events import event_bus


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite limpo para cada teste (LF_API_TEST=1)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    # Remove o banco E os arquivos WAL/SHM: em journal_mode=WAL, remover só o
    # .sqlite e deixar o -wal órfão causa "disk I/O error" na próxima abertura.
    for f in (
        ".loopforge/test_api.sqlite",
        ".loopforge/test_api.sqlite-wal",
        ".loopforge/test_api.sqlite-shm",
    ):
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    # Garante que nenhum WAL órfão polua o próximo teste do módulo/suíte.
    for f in (".loopforge/test_api.sqlite-wal", ".loopforge/test_api.sqlite-shm"):
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest.mark.asyncio
async def test_publish_persiste_envelope_v1_com_seq_incremental():
    """Dois publishes na mesma run geram seq 1 e 2, persistidos no journal."""
    env1 = await event_bus.publish(
        "run-1", "run_created", {"idea": "Build login", "status": "pending"}
    )
    env2 = await event_bus.publish(
        "run-1", "node_execution", {"node": "cpo", "status": "completed"}
    )

    # Shape exato do envelope v1 (contrato)
    assert set(env1) == {"seq", "event", "run_id", "timestamp", "payload"}
    assert env1["seq"] == 1
    assert env2["seq"] == 2
    assert env1["event"] == "run_created"
    assert env1["run_id"] == "run-1"
    assert env1["payload"] == {"idea": "Build login", "status": "pending"}
    assert isinstance(env1["timestamp"], str) and env1["timestamp"]
    assert env2["event"] == "node_execution"
    assert env2["payload"] == {"node": "cpo", "status": "completed"}

    # Persistido no journal: list_events devolve os mesmos envelopes em ordem
    persisted = await event_bus.list_events("run-1")
    assert [e["seq"] for e in persisted] == [1, 2]
    assert persisted[0] == env1
    assert persisted[1] == env2


@pytest.mark.asyncio
async def test_list_events_after_seq_e_limit():
    """list_events suporta after_seq e limit para backfill paginado."""
    for i in range(1, 4):
        await event_bus.publish("run-2", "run_updated", {"n": i})

    todos = await event_bus.list_events("run-2")
    assert [e["seq"] for e in todos] == [1, 2, 3]

    after1 = await event_bus.list_events("run-2", after_seq=1)
    assert [e["seq"] for e in after1] == [2, 3]

    limit2 = await event_bus.list_events("run-2", after_seq=0, limit=2)
    assert [e["seq"] for e in limit2] == [1, 2]

    assert await event_bus.list_events("run-2", after_seq=99) == []
    assert await event_bus.list_events("run-inexistente") == []


@pytest.mark.asyncio
async def test_seq_independente_por_run():
    """Runs diferentes têm seq independentes (cada run começa em 1)."""
    a1 = await event_bus.publish("run-a", "run_created", {})
    b1 = await event_bus.publish("run-b", "run_created", {})
    a2 = await event_bus.publish("run-a", "run_updated", {"status": "running"})

    assert a1["seq"] == 1
    assert b1["seq"] == 1
    assert a2["seq"] == 2


def test_publish_sem_loop_ativo_fallback():
    """Sem event loop ativo, agendar o broadcast não levanta (fallback: apenas persiste)."""
    # Teste síncrono: não há loop ativo, então get_running_loop() levanta
    # RuntimeError, que _broadcast engole — o fallback do EventBus.
    event_bus._broadcast(
        {"seq": 1, "event": "x", "run_id": "run-x", "timestamp": "t", "payload": {}}
    )
