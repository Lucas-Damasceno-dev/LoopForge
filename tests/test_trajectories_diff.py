"""Testes do diff entre checkpoints (pilar time-travel profundo).

Cobre ``GET /api/v1/trajectories/{thread}/diff?from=&to=`` (added/removed/
changed, sanitização de valores não-serializáveis, preview truncado, 404 de
thread/checkpoint) e a evolução BC de ``GET .../checkpoints?detail=1``
(metadados de id/parent/ts/step/node SEM quebrar a resposta default
``[{thread_id}]`` nem os endpoints de checkpoint/fork existentes).

Mesmo padrão hermético de test_api_trajectories_fork_export (LF_API_TEST=1 +
init_db + tmp_path): cada teste roda com trajectories.db próprio.
"""

import contextlib
import os
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


async def _seed_thread(thread_id: str, checkpoint_ids: tuple[str, ...], states: list[dict]) -> None:
    """Grava checkpoints direto no checkpointer (sem passar pela API)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        for i, cid in enumerate(checkpoint_ids):
            await saver.aput(
                {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}},
                {
                    "id": cid,
                    "v": 1,
                    "ts": f"2026-08-05T00:00:{i:02d}Z",
                    "channel_values": states[i],
                },
                {"source": "loop", "step": i},
                {},
            )
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
async def test_diff_added_removed_changed():
    """(a) Diff: added/removed/changed corretos com previews JSON-safe."""
    thread = f"run-{uuid.uuid4()}"
    states = [
        {"next_agent": "cpo", "idea": "original", "drop_me": "bye", "messages": ["a"]},
        {"next_agent": "pm", "idea": "original", "messages": ["a", "b"], "extra": {"x": 1}},
    ]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1", "to": "seed-2"})
        assert r.status_code == 200
        data = r.json()
        assert data["thread_id"] == thread
        assert data["from"] == "seed-1"
        assert data["to"] == "seed-2"

        # added: chave só no destino (preview JSON do dict)
        assert data["added"] == {"extra": '{"x": 1}'}
        # removed: chave só na origem (preview JSON da string)
        assert data["removed"] == {"drop_me": '"bye"'}
        # changed: valores diferentes em ambos (ordem do estado destino)
        assert data["changed"] == [
            {"key": "next_agent", "before": '"cpo"', "after": '"pm"'},
            {"key": "messages", "before": '["a"]', "after": '["a", "b"]'},
        ]


@pytest.mark.asyncio
async def test_diff_sem_mudanca_vazio():
    """(b) Diff de checkpoints idênticos: três listas/dicts vazios."""
    thread = f"run-{uuid.uuid4()}"
    state = {"next_agent": "qa", "idea": "same"}
    await _seed_thread(thread, ("seed-1", "seed-2"), [dict(state), dict(state)])

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1", "to": "seed-2"})
        assert r.status_code == 200
        data = r.json()
        assert data["added"] == {}
        assert data["removed"] == {}
        assert data["changed"] == []


class _BadStr:
    """Valor com str() que falha — deve cair no marcador <unserializable>."""

    def __str__(self) -> str:
        raise ValueError("no str")


@pytest.mark.asyncio
async def test_diff_sanitiza_nao_serializaveis_e_mascara_sensiveis():
    """(c) Sanitização: valor não-serializável vira marcador; api_key → redacted."""
    thread = f"run-{uuid.uuid4()}"
    states = [
        {"good": "ok"},
        {"bad": _BadStr(), "api_key": "sk-123-secret"},
    ]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1", "to": "seed-2"})
        assert r.status_code == 200
        data = r.json()
        # valor não-serializável sanitizado (não quebra o payload)
        assert data["added"]["bad"] == "<unserializable _BadStr>"
        # chave sensível mascarada mesmo com valor serializável
        assert data["added"]["api_key"] == "<redacted>"


@pytest.mark.asyncio
async def test_diff_preview_truncado_500():
    """(d) Preview truncado em 500 chars (+ ellipsis) para valores grandes."""
    thread = f"run-{uuid.uuid4()}"
    big = "x" * 600
    states = [{"small": "ok"}, {"big": big}]
    await _seed_thread(thread, ("seed-1", "seed-2"), states)

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1", "to": "seed-2"})
        assert r.status_code == 200
        preview = r.json()["added"]["big"]
        assert len(preview) == 501  # 500 chars + "…"
        assert preview.endswith("…")
        # preview JSON da string mantém as aspas iniciais (json.dumps)
        assert preview[0] == '"'


@pytest.mark.asyncio
async def test_diff_thread_inexistente_404():
    """(e) Diff de thread sem trajetória → 404."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(
            f"/api/v1/trajectories/run-{uuid.uuid4()}/diff",
            params={"from": "seed-1", "to": "seed-2"},
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_diff_checkpoint_inexistente_404():
    """(f) Diff com from/to ausente da thread → 404 (mensagem com o id)."""
    thread = f"run-{uuid.uuid4()}"
    await _seed_thread(thread, ("seed-1", "seed-2"), [{"a": 1}, {"a": 2}])

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r_from = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "ghost", "to": "seed-2"})
        assert r_from.status_code == 404
        assert r_from.json()["detail"] == "Checkpoint ghost não encontrado"

        r_to = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1", "to": "ghost"})
        assert r_to.status_code == 404
        assert r_to.json()["detail"] == "Checkpoint ghost não encontrado"


@pytest.mark.asyncio
async def test_diff_sem_query_params_422():
    """(g) Diff sem from/to (query obrigatória) → 422 do FastAPI."""
    thread = f"run-{uuid.uuid4()}"
    await _seed_thread(thread, ("seed-1", "seed-2"), [{"a": 1}, {"a": 2}])

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/v1/trajectories/{thread}/diff")
        assert r.status_code == 422
        r2 = await ac.get(f"/api/v1/trajectories/{thread}/diff", params={"from": "seed-1"})
        assert r2.status_code == 422


@pytest.mark.asyncio
async def test_checkpoints_detail_enriquece_sem_quebrar_bc():
    """(h) BC: GET /checkpoints default segue [{thread_id}]; ?detail=1 enriquece.

    Os metadados (checkpoint_id, parent_checkpoint_id, ts, step, node) são
    adicionados SEM quebrar o contrato default (Fase C). O GET de checkpoint
    individual também segue funcionando.
    """
    thread = f"run-{uuid.uuid4()}"
    await _seed_thread(thread, ("seed-1", "seed-2"), [{"next_agent": "cpo"}, {"next_agent": "pm"}])

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # default (BC): resposta exata da Fase C
        r = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints")
        assert r.status_code == 200
        assert r.json() == [{"thread_id": thread}]

        # detail=1: metadados em ordem cronológica (seed-1 → seed-2)
        rd = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints", params={"detail": "1"})
        assert rd.status_code == 200
        entries = rd.json()
        assert [e["checkpoint_id"] for e in entries] == ["seed-1", "seed-2"]
        assert entries[0]["ts"] == "2026-08-05T00:00:00Z"
        assert entries[0]["step"] == 0
        assert entries[1]["step"] == 1
        assert all(e["thread_id"] == thread for e in entries)
        assert all(e["node"] is None for e in entries)  # sem writes no seed

        # GET individual segue intacto (BC)
        rc = await ac.get(f"/api/v1/trajectories/{thread}/checkpoints/seed-1")
        assert rc.status_code == 200
        assert rc.json()["state"] == {"next_agent": "cpo"}


@pytest.mark.asyncio
async def test_checkpoints_detail_thread_inexistente_vazio():
    """(i) ?detail=1 de thread sem trajetória → [] (sem 404, BC da listagem)."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(
            f"/api/v1/trajectories/run-{uuid.uuid4()}/checkpoints",
            params={"detail": "1"},
        )
        assert r.status_code == 200
        assert r.json() == []
