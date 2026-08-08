"""Testes C5 (M-02): timeline unificada por run_id — eventos + checkpoints.

GET /api/v1/runs/{run_id}/timeline devolve itens ``{seq, type, timestamp,
node, data}`` intercalando o journal (tabela ``events``) com os checkpoints
LangGraph da thread canônica ``run-{id}`` (trajectories.db, ADR-0003),
ordenados cronologicamente. Cobre: merge dos dois streams, paginação
``after_seq``/``limit``, alias legado com Sunset/Deprecation (M-18) e 404
para run inexistente.
"""

import asyncio
import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_events_backfill.py)."""
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


async def _run_mock_pipeline(client: AsyncClient, idea: str = "Timeline") -> tuple[str, str]:
    """Cria e espera uma pipeline mock terminar; devolve (run_id, status)."""
    resp = await client.post("/api/runs", json={"idea": idea, "stack": "python", "mock_llm": True})
    assert resp.status_code == 201
    run_id = resp.json()["id"]
    waited = 0.0
    while waited < 30.0:
        status = (await client.get(f"/api/runs/{run_id}")).json()["status"]
        if status in ("completed", "failed", "paused"):
            return run_id, status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em 30s")


def _assert_item_shape(item: dict) -> None:
    """Item da timeline segue o contrato {seq, type, timestamp, node, data}."""
    assert set(item) == {"seq", "type", "timestamp", "node", "data"}, f"shape quebrado: {set(item)}"
    assert isinstance(item["seq"], int)
    assert item["type"] in ("event", "checkpoint")
    assert isinstance(item["timestamp"], str) and item["timestamp"]
    assert isinstance(item["data"], dict)


@pytest.mark.asyncio
async def test_timeline_merge_eventos_e_checkpoints():
    """Timeline intercala eventos do journal + checkpoints LangGraph da run."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, status = await _run_mock_pipeline(client, idea="Timeline merge")
        assert status == "completed"

        resp = await client.get(f"/api/v1/runs/{run_id}/timeline")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        timeline = data["timeline"]
        assert timeline, "timeline vazia para run com pipeline"
        assert data["total_count"] == len(timeline)

        # Contrato do item + seq 1..N estritamente incremental
        for item in timeline:
            _assert_item_shape(item)
        seqs = [item["seq"] for item in timeline]
        assert seqs == list(range(1, len(seqs) + 1)), f"seq quebrado: {seqs}"

        # Timestamps em ordem não decrescente (cronológica)
        stamps = [item["timestamp"] for item in timeline]
        assert stamps == sorted(stamps), "timeline fora de ordem cronológica"

        # Pipeline mock grava checkpoints no trajectories.db: os DOIS tipos aparecem
        types = {item["type"] for item in timeline}
        assert types == {"event", "checkpoint"}, f"esperado event+checkpoint, veio {types}"

        # Eventos: node vem do payload quando disponível; data é o payload
        events = [item for item in timeline if item["type"] == "event"]
        node_exec = [item for item in events if item["data"].get("node")]
        assert node_exec, "nenhum evento node_execution com node no payload"
        assert all(item["node"] == item["data"]["node"] for item in node_exec)

        # Checkpoints: data serializado (checkpoint_id, parent_checkpoint_id,
        # type, metadata, checkpoint) com timestamp do blob alinhado ao item
        checkpoints = [item for item in timeline if item["type"] == "checkpoint"]
        for cp in checkpoints:
            d = cp["data"]
            assert d["checkpoint_id"]
            assert "parent_checkpoint_id" in d
            assert isinstance(d["metadata"], dict)
            assert isinstance(d["checkpoint"], dict)
            assert d["checkpoint"]["ts"] == cp["timestamp"]
        # A timeline começa com o evento run_created (envelope v1)
        assert timeline[0]["type"] == "event"
        assert timeline[0]["data"].get("idea") == "Timeline merge"


@pytest.mark.asyncio
async def test_timeline_paginacao_after_seq_limit():
    """Paginação: after_seq/limit fatiam a timeline merged sem perder itens."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, _ = await _run_mock_pipeline(client, idea="Timeline paginação")

        # Aguarda a timeline estabilizar: o status "completed" chega antes de
        # eventos tardios (run_updated/pipeline_finished), o que mudaria o
        # total_count no MEIO da paginação e quebraria a reconstrução final.
        todos: list[dict] = []
        for _ in range(30):
            before = (await client.get(f"/api/v1/runs/{run_id}/timeline")).json()["timeline"]
            await asyncio.sleep(0.2)
            after = (await client.get(f"/api/v1/runs/{run_id}/timeline")).json()["timeline"]
            if len(before) == len(after):
                todos = after
                break
        total = len(todos)
        assert total >= 10, f"esperado timeline com vários itens, veio {total}"

        # Página 1: limit=5 → seq 1..5 + has_more/next_after_seq
        p1 = (await client.get(f"/api/v1/runs/{run_id}/timeline", params={"limit": 5})).json()
        assert [it["seq"] for it in p1["timeline"]] == [1, 2, 3, 4, 5]
        assert p1["total_count"] == total
        assert p1["has_more"] is True
        assert p1["next_after_seq"] == 5

        # Página 2: after_seq=5, limit=5 → seq 6..10
        p2 = (await client.get(f"/api/v1/runs/{run_id}/timeline", params={"after_seq": 5, "limit": 5})).json()
        assert [it["seq"] for it in p2["timeline"]] == [6, 7, 8, 9, 10]
        assert p2["has_more"] is True

        # Percorre as demais páginas e reconstrói a timeline completa
        concatenated = p1["timeline"] + p2["timeline"]
        after = p2["next_after_seq"]
        while True:
            page = (await client.get(f"/api/v1/runs/{run_id}/timeline", params={"after_seq": after, "limit": 5})).json()
            concatenated += page["timeline"]
            if not page["has_more"]:
                assert page["next_after_seq"] is None
                break
            after = page["next_after_seq"]
        assert [it["seq"] for it in concatenated] == list(range(1, total + 1))

        # after_seq além do fim → página vazia, has_more False
        beyond = (await client.get(f"/api/v1/runs/{run_id}/timeline", params={"after_seq": 9999})).json()
        assert beyond["timeline"] == [] and beyond["has_more"] is False


@pytest.mark.asyncio
async def test_timeline_alias_legado_headers():
    """Alias legado /api/runs/{id}/timeline delega com Sunset/Deprecation (M-18)."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        run_id, _ = await _run_mock_pipeline(client, idea="Alias timeline")

        resp = await client.get(f"/api/runs/{run_id}/timeline")
        assert resp.status_code == 200
        assert resp.headers.get("Sunset") == "2026-12-31"
        assert resp.headers.get("Deprecation") == "true"
        assert resp.json()["run_id"] == run_id
        assert resp.json()["timeline"]


@pytest.mark.asyncio
async def test_timeline_404_run_inexistente():
    """GET /timeline de run inexistente → 404."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/runs/nao-existe/timeline")
        assert resp.status_code == 404
