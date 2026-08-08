"""Testes dedicados do POST /import (M-14) — materialização de trajetórias.

Cobre os cenários do spec de QA do import:

1. Materialização real: thread criada, checkpoints gravados, PipelineRun criada.
2. Validação 422 (payload sem campos obrigatórios / estrutura malformada).
3. Lista de checkpoints vazia → erro apropriado (defeito conhecido, xfail).
4. Preservação de ordem e encadeamento parent_checkpoint_id.
5. Idempotência: reimport na mesma thread não duplica checkpoints (contrato V1: 409).

Casos de borda extras: state não-dict (coerção silenciosa), checkpoint sem ts,
run_id reutilizado (upsert de pipeline_runs) e parent inexistente.

Mesmo padrão endurecido de test_api_trajectories_fork_export.py: LF_API_TEST=1
+ init_db em tmp_path hermético (.loopforge/ isolado por teste).
"""

import contextlib
import os
import sqlite3
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


def _payload(run_id: str, thread_id: str, checkpoints: list[dict], **extra) -> dict:
    """Monta um payload de export válido (schema_version 1.1)."""
    base = {
        "schema_version": "1.1",
        "run_id": run_id,
        "thread_id": thread_id,
        "exported_at": "2026-08-05T00:00:00Z",
        "idea": "ideia de teste",
        "checkpoints": checkpoints,
    }
    base.update(extra)
    return base


def _fetch_pipeline_run(run_id: str) -> tuple | None:
    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        return conn.execute(
            "SELECT id, status, thread_id, idea FROM pipeline_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()


async def _alist_thread(thread_id: str) -> list[tuple[str | None, str | None]]:
    """Lista (checkpoint_id, parent_checkpoint_id) em ordem DESC do saver."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        pairs = []
        async for item in saver.alist({"configurable": {"thread_id": thread_id}}):
            cfg = (item.config or {}).get("configurable", {})
            parent = (item.parent_config or {}).get("configurable", {}).get("checkpoint_id")
            pairs.append((cfg.get("checkpoint_id"), parent))
        return pairs
    finally:
        await saver.conn.close()


async def _count_checkpoints(thread_id: str) -> int:
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        async with saver.conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = ?", (thread_id,)) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0
    finally:
        await saver.conn.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    """Banco SQLite limpo em tmp_path para cada teste (LF_API_TEST=1)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()
    for f in (".loopforge/test_api.sqlite-wal", ".loopforge/test_api.sqlite-shm"):
        with contextlib.suppress(Exception):
            os.remove(f)
    monkeypatch.delenv("LF_API_TEST", raising=False)


@pytest.mark.asyncio
async def test_import_materializa_checkpoints_e_cria_pipeline_run():
    """(1) Import válido: thread criada, checkpoints materializados, PipelineRun queued."""
    run_id = str(uuid.uuid4())
    thread_id = "t-mat"
    cps = [
        {"checkpoint_id": "c1", "state": {"idea": "login"}},
        {"checkpoint_id": "c2", "state": {"idea": "login", "next_agent": "pm"}},
    ]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r.status_code == 201
        assert r.json() == {
            "run_id": run_id,
            "thread_id": thread_id,
            "checkpoints_imported": 2,
        }

        # thread listável
        rl = await ac.get(f"/api/v1/trajectories/{thread_id}/checkpoints")
        assert rl.status_code == 200
        assert rl.json() == [{"thread_id": thread_id}]

        # estados materializados integralmente
        for cid, st in (("c1", {"idea": "login"}), ("c2", {"idea": "login", "next_agent": "pm"})):
            rc = await ac.get(f"/api/v1/trajectories/{thread_id}/checkpoints/{cid}")
            assert rc.status_code == 200
            assert rc.json()["state"] == st

        # PipelineRun criada com thread_id correto e status queued
        row = _fetch_pipeline_run(run_id)
        assert row is not None
        assert row[1] == "queued"
        assert row[2] == thread_id
        assert row[3] == "ideia de teste"


@pytest.mark.asyncio
async def test_import_payload_invalido_422():
    """(2) Payload sem campos obrigatórios / malformado → 422 com mensagem PT."""
    cases = [
        # sem schema_version
        {"run_id": "x", "thread_id": "y", "checkpoints": []},
        # schema_version fora do suportado
        {"schema_version": "1.0", "run_id": "x", "thread_id": "y", "checkpoints": []},
        # sem run_id
        {"schema_version": "1.1", "thread_id": "y", "checkpoints": []},
        # run_id vazio
        {"schema_version": "1.1", "run_id": "", "thread_id": "y", "checkpoints": []},
        # sem thread_id
        {"schema_version": "1.1", "run_id": "x", "checkpoints": []},
        # thread_id vazio
        {"schema_version": "1.1", "run_id": "x", "thread_id": "", "checkpoints": []},
        # checkpoints não-lista
        {"schema_version": "1.1", "run_id": "x", "thread_id": "y", "checkpoints": "nope"},
        # checkpoint sem checkpoint_id
        {"schema_version": "1.1", "run_id": "x", "thread_id": "y", "checkpoints": [{"ts": "t"}]},
        # checkpoint_id vazio
        {
            "schema_version": "1.1",
            "run_id": "x",
            "thread_id": "y",
            "checkpoints": [{"checkpoint_id": "", "state": {}}],
        },
        # checkpoint não-objeto
        {
            "schema_version": "1.1",
            "run_id": "x",
            "thread_id": "y",
            "checkpoints": [42],
        },
    ]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for i, payload in enumerate(cases):
            r = await ac.post("/api/v1/trajectories/import", json=payload)
            assert r.status_code == 422, f"caso {i} ({payload}) -> {r.status_code} {r.text}"
            assert "detail" in r.json()


@pytest.mark.asyncio
@pytest.mark.xfail(
    strict=False,
    reason="Defeito M-14: import aceita checkpoints=[] e retorna 201/0 em vez de erro — ver relatório QA",
)
async def test_import_vazio_sem_checkpoints_erro():
    """(3) Lista de checkpoints vazia → erro apropriado (spec exige erro).

    Comportamento atual (defeito): retorna 201 com ``checkpoints_imported: 0``
    e ainda cria uma PipelineRun 'queued' sem nenhuma trajetória. O spec M-14
    exige rejeição com erro (400/422). Ver sugestão de correção no relatório.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/v1/trajectories/import",
            json=_payload(str(uuid.uuid4()), "t-empty", []),
        )
        assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_import_preserva_ordem_checkpoints():
    """(4) 3 checkpoints encadeados: ordem e links parent preservados."""
    run_id = str(uuid.uuid4())
    thread_id = "t-order"
    cps = [
        {"checkpoint_id": "c1", "parent_checkpoint_id": None, "step": 0, "state": {"idea": "1"}},
        {"checkpoint_id": "c2", "parent_checkpoint_id": "c1", "step": 1, "state": {"idea": "2"}},
        {"checkpoint_id": "c3", "parent_checkpoint_id": "c2", "step": 2, "state": {"idea": "3"}},
    ]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r.status_code == 201
        assert r.json()["checkpoints_imported"] == 3

    # alist é DESC (head primeiro) → c3 → c2 → c1 com parents encadeados
    pairs = await _alist_thread(thread_id)
    assert pairs == [("c3", "c2"), ("c2", "c1"), ("c1", None)]


@pytest.mark.asyncio
async def test_import_idempotente():
    """(5) Reimport do mesmo payload: 409 (contrato V1) e NENHUMA duplicata."""
    run_id = str(uuid.uuid4())
    thread_id = "t-idem"
    cps = [
        {"checkpoint_id": "c1", "state": {"idea": "login"}},
        {"checkpoint_id": "c2", "state": {"idea": "login"}},
    ]
    payload = _payload(run_id, thread_id, cps)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/api/v1/trajectories/import", json=payload)
        assert r1.status_code == 201
        assert r1.json()["checkpoints_imported"] == 2

        # segunda vez: sem merge no V1 → 409, sem duplicatas
        r2 = await ac.post("/api/v1/trajectories/import", json=payload)
        assert r2.status_code == 409
        assert "sem merge" in r2.json()["detail"]

        # mesma thread continua com exatamente 2 checkpoints (nenhuma duplicata)
        assert await _count_checkpoints(thread_id) == 2


@pytest.mark.asyncio
async def test_import_state_nao_dict_nao_quebra():
    """(6) state não-dict (string) é coerção silenciosa para {} — sem crash.

    Observação QA: o import não rejeita nem avisa quando ``state`` não é um
    dict; materializa ``{}``. Para o payload vindo da API REST isso só ocorre
    se o cliente mandar dado inconsistente — registrado como edge case.
    """
    run_id = str(uuid.uuid4())
    thread_id = "t-state"
    cps = [{"checkpoint_id": "c1", "state": "not-a-dict"}]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r.status_code == 201
        rc = await ac.get(f"/api/v1/trajectories/{thread_id}/checkpoints/c1")
        assert rc.status_code == 200
        assert rc.json()["state"] == {}


@pytest.mark.asyncio
async def test_import_checkpoint_sem_ts_usa_agora():
    """(7) Checkpoint sem ts → materializado sem crash (usa _now())."""
    run_id = str(uuid.uuid4())
    thread_id = "t-nots"
    cps = [{"checkpoint_id": "c1", "state": {"idea": "x"}}]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r.status_code == 201
        assert r.json()["checkpoints_imported"] == 1
        rc = await ac.get(f"/api/v1/trajectories/{thread_id}/checkpoints/c1")
        assert rc.status_code == 200
        assert rc.json()["state"] == {"idea": "x"}


@pytest.mark.asyncio
async def test_import_parent_inexistente_nao_quebra():
    """(8) parent_checkpoint_id apontando para checkpoint ausente — import segue ok.

    Edge case: o link fica "pendurado" (dangling) sem validação. O import não
    valida referencialmente os parents; documentado como comportamento atual.
    """
    run_id = str(uuid.uuid4())
    thread_id = "t-dangling"
    cps = [
        {"checkpoint_id": "c1", "parent_checkpoint_id": "nao-existe", "state": {"idea": "x"}},
    ]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r.status_code == 201
        assert r.json()["checkpoints_imported"] == 1


@pytest.mark.asyncio
async def test_import_run_id_reutilizado_atualiza_pipeline_run():
    """(9) run_id já existente em pipeline_runs → upsert (não duplica a linha)."""
    run_id = str(uuid.uuid4())
    thread_id = "t-upsert"
    cps = [{"checkpoint_id": "c1", "state": {"idea": "v1"}}]

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r1 = await ac.post("/api/v1/trajectories/import", json=_payload(run_id, thread_id, cps))
        assert r1.status_code == 201

        # segundo import com MESMO run_id mas thread nova → upsert da PipelineRun
        r2 = await ac.post(
            "/api/v1/trajectories/import",
            json=_payload(run_id, "t-upsert-2", [{"checkpoint_id": "c2", "state": {"idea": "v2"}}]),
        )
        assert r2.status_code == 201

        conn = sqlite3.connect(".loopforge/telemetry.sqlite")
        try:
            rows = conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE id = ?", (run_id,)).fetchone()
            assert rows[0] == 1  # upsert, não duplicou
        finally:
            conn.close()
