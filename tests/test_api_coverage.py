"""Cobertura adicional de branches da API principal."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    db_file = ".loopforge/test_api.sqlite"
    if os.path.exists(db_file):
        os.remove(db_file)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)
    os.environ.pop("LF_API_KEY", None)


@pytest_asyncio.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_and_dashboard_and_process_time_header(client: AsyncClient):
    r1 = await client.get("/")
    r2 = await client.get("/dashboard")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert "X-Process-Time" in r1.headers
    assert "LoopForge v6" in r1.text


@pytest.mark.asyncio
async def test_create_run_payload_invalido_retorna_422(client: AsyncClient):
    resp = await client.post("/api/runs", json={"stack": "python"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_runs_com_paginacao(client: AsyncClient):
    for i in range(3):
        await client.post("/api/runs", json={"idea": f"run-{i}"})
    resp = await client.get("/api/runs?skip=1&limit=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1


@pytest.mark.asyncio
async def test_get_patch_delete_execute_resume_404(client: AsyncClient):
    rid = "inexistente"
    assert (await client.get(f"/api/runs/{rid}")).status_code == 404
    assert (await client.patch(f"/api/runs/{rid}", json={"status": "running"})).status_code == 404
    assert (await client.delete(f"/api/runs/{rid}")).status_code == 404
    assert (await client.post(f"/api/runs/{rid}/execute")).status_code == 404
    assert (await client.post(f"/api/runs/{rid}/resume")).status_code == 404


@pytest.mark.asyncio
async def test_execute_and_resume_existing_run(monkeypatch, client: AsyncClient):
    resp = await client.post("/api/runs", json={"idea": "x"})
    run_id = resp.json()["id"]

    # Impede execução real da pipeline em background (sem LLM/rede).
    monkeypatch.setattr("lf.api.app._execute_pipeline_in_background", AsyncMock())

    async def _noop():
        return {}

    monkeypatch.setattr("asyncio.to_thread", lambda *_a, **_k: _noop())

    r1 = await client.post(f"/api/runs/{run_id}/execute")
    r2 = await client.post(f"/api/runs/{run_id}/resume")
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.asyncio
async def test_record_human_decision_dispara_broadcast(monkeypatch, client: AsyncClient):
    """Contrato B1 (A1): decide fora de gate pendente é REJEITADO com 409.

    Run criada mock SEM interactive → termina sem gate; o POST /decide não
    registra decisão nem emite human_decision_submitted (antes aceitava
    qualquer coisa com 201 — bug do audit).
    """
    run_resp = await client.post("/api/runs", json={"idea": "decisao"})
    run_id = run_resp.json()["id"]
    broadcast = AsyncMock()
    monkeypatch.setattr("lf.api.app.ws_manager.broadcast", broadcast)
    payload = {
        "gate_node": "qa",
        "action": "approve",
        "feedback_category": "ok",
        "feedback_message": "pode seguir",
        "user": "tester",
    }
    resp = await client.post(f"/api/runs/{run_id}/decide", json=payload)
    # 409: run sem gate pendente (completed/inexistente) não aceita decisão.
    assert resp.status_code == 409
    detail = str(resp.json()["detail"])
    assert "não aceita decisões" in detail or "no pending decision" in detail
    assert broadcast.await_count == 0

    # Run inexistente → 404 (e nada broadcastado).
    nf = await client.post(
        f"/api/runs/{'nao-existe'}/decide",
        json={"gate_node": "qa", "action": "approve"},
    )
    assert nf.status_code == 404
    assert broadcast.await_count == 0


def test_websocket_auth_rejeita_token_invalido():
    os.environ["LF_API_REQUIRE_AUTH"] = "true"
    os.environ["LF_API_KEY"] = "token-certo"
    app = create_app()
    with TestClient(app) as tc:
        with pytest.raises(Exception):
            with tc.websocket_connect("/ws/streaming?token=token-errado"):
                pass


def test_websocket_ping_pong():
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    app = create_app()
    with TestClient(app) as tc:
        with tc.websocket_connect("/ws/runs/abc") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "connected"
            ws.send_json({"type": "ping"})
            pong = ws.receive_json()
            assert pong["type"] == "pong"


def test_websocket_heartbeat_ping(monkeypatch):
    """Heartbeat app-level (item 2): socket ocioso recebe {'type':'ping'}.

    O intervalo é reduzido via monkeypatch para o teste não esperar 30s; o
    frontend responde {'type':'pong'} (ignorado pelo servidor — sem loop).
    """
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    from lf.api.app import WS_HEARTBEAT_INTERVAL

    monkeypatch.setattr("lf.api.app.WS_HEARTBEAT_INTERVAL", 0.2)
    assert WS_HEARTBEAT_INTERVAL == 30.0  # default prod preservado
    app = create_app()
    with TestClient(app) as tc:
        with tc.websocket_connect("/ws/runs/abc") as ws:
            msg = ws.receive_json()
            assert msg["event"] == "connected"
            # Sem mensagens do cliente → servidor envia ping do heartbeat.
            ping = ws.receive_json()
            assert ping == {"type": "ping"}
            ws.send_json({"type": "pong"})
