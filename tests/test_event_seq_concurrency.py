"""Testes de concorrência de seq do EventBus (race COUNT+1 → UPDATE...RETURNING).

Reproduz o bug: publishes concorrentes na MESMA run geravam seq duplicado
(``_next_seq`` com COUNT+1 não-atômico). Com a tabela ``event_seq``
(incremento atômico ``UPDATE ... RETURNING`` na mesma transação do INSERT),
seqs são únicos, contíguos e estritamente crescentes por run.
"""

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio

from lf.api.database import close_db, init_db
from lf.api.events import Event, event_bus

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_event_envelope.py)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest.mark.asyncio
async def test_publishes_concorrentes_sem_seq_duplicado():
    """25 publishes concorrentes na mesma run → seq únicos e contíguos 1..25."""
    n = 25
    envelopes = await asyncio.gather(*(event_bus.publish("run-conc", "node_execution", {"n": i}) for i in range(n)))
    seqs = sorted(env["seq"] for env in envelopes)
    assert seqs == list(range(1, n + 1)), f"seq duplicado/quebrado: {seqs}"
    assert len(set(seqs)) == n

    # Journal consistente com o envelope: contiguidade preservada no backfill
    persisted = await event_bus.list_events("run-conc")
    assert [e["seq"] for e in persisted] == list(range(1, n + 1))


@pytest.mark.asyncio
async def test_concorrencia_entre_runs_mantem_independencia():
    """Publishes concorrentes em 2 runs: seq independentes (cada run em 1..N)."""
    await asyncio.gather(
        event_bus.publish("run-x", "run_updated", {"n": 1}),
        event_bus.publish("run-y", "run_updated", {"n": 1}),
        event_bus.publish("run-x", "run_updated", {"n": 2}),
        event_bus.publish("run-y", "run_updated", {"n": 2}),
        event_bus.publish("run-x", "run_updated", {"n": 3}),
    )

    seqs_x = [e["seq"] for e in await event_bus.list_events("run-x")]
    seqs_y = [e["seq"] for e in await event_bus.list_events("run-y")]
    assert seqs_x == [1, 2, 3], f"seq run-x quebrado: {seqs_x}"
    assert seqs_y == [1, 2], f"seq run-y quebrado: {seqs_y}"


@pytest.mark.asyncio
async def test_seq_contiguo_apos_seed_de_runs_legadas():
    """Runs com eventos pré-existentes (seed do init_db) seguem do MAX(seq)."""
    from sqlalchemy import text

    from lf.api.database import Base, engine, session_factory

    async with session_factory() as session:
        # Simula journal legado sem contador: eventos com seq 1..2, sem event_seq
        session.add_all(
            [
                Event(run_id="run-legacy", seq=1, event_type="run_created", payload={}),
                Event(run_id="run-legacy", seq=2, event_type="run_updated", payload={}),
            ]
        )
        await session.commit()
        await session.execute(text("DELETE FROM event_seq WHERE run_id = 'run-legacy'"))
        await session.commit()

    # Mesma semeadura do init_db (INSERT..SELECT MAX(seq)..ON CONFLICT DO NOTHING)
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                text(
                    "INSERT INTO event_seq (run_id, last_seq) "
                    "SELECT run_id, MAX(seq) FROM events GROUP BY run_id "
                    "ON CONFLICT (run_id) DO NOTHING"
                )
            )

    env = await event_bus.publish("run-legacy", "run_updated", {"status": "running"})
    assert env["seq"] == 3, f"seq pós-seed deveria continuar em 3, veio {env['seq']}"

    persisted = [e["seq"] for e in await event_bus.list_events("run-legacy")]
    assert persisted == [1, 2, 3], f"journal legado perdeu contiguidade: {persisted}"
