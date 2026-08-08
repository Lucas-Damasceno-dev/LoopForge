"""Testes M-06 (A4, n2b): canal WS filtrado por run + streaming global.

- ``/ws/runs/{run_id}`` registra o cliente no canal da run: recebe envelope v1
  (``{seq, event, run_id, timestamp, payload}``) com seq incremental e SÓ
  eventos daquele run.
- ``/ws/streaming`` segue global: recebe os mesmos eventos, inclusive
  ``run_created`` (conexão anterior à criação).
- Auth: com ``LF_API_REQUIRE_AUTH=true`` a conexão exige ``?token=`` correto
  (token inválido é rejeitado com 1008).
"""
import contextlib
import os
import time

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db

TERMINAL_EVENTS = ("pipeline_finished", "pipeline_failed", "pipeline_error")
ENVELOPE_V1 = {"seq", "event", "run_id", "timestamp", "payload"}
TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


def _wipe_db_files():
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_api.py/test_event_envelope.py)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    _wipe_db_files()
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    # WAL/SHM órfãos poluem o próximo teste — remove sempre.
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)
    os.environ.pop("LF_API_API_KEY", None)


def _collect_events(ws, timeout: float = 25.0) -> list[dict]:
    """Coleta envelopes v1 até um evento terminal (ou a conexão fechar).

    Mensagens de controle (``connected``/``pong``) não são envelopes v1 e são
    ignoradas. O evento terminal (pipeline_finished/failed/error) encerra a
    coleta — a pipeline mock termina em ~1-2s.
    """
    events: list[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            msg = ws.receive_json()
        except Exception:
            break  # conexão fechada pelo servidor
        if set(msg) != ENVELOPE_V1:
            continue
        events.append(msg)
        if msg["event"] in TERMINAL_EVENTS:
            break
    return events


def test_ws_run_channel_receives_only_run_events(monkeypatch):
    """/ws/runs/{run_id} (com token) recebe SÓ envelopes v1 daquele run, seq incremental."""
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", "test-key")  # APISettings: env_prefix LF_API_
    app = create_app()
    headers = {"X-API-Key": "test-key"}

    with TestClient(app) as tc:
        resp = tc.post(
            "/api/runs",
            json={"idea": "WS run filter", "stack": "python", "mock_llm": True},
            headers=headers,
        )
        assert resp.status_code == 201
        run_id = resp.json()["id"]

        with tc.websocket_connect(f"/ws/runs/{run_id}?token=test-key") as ws:
            first = ws.receive_json()
            assert first["event"] == "connected"

            events = _collect_events(ws)
            assert events, "nenhum envelope v1 recebido no canal da run"

            # Shape envelope v1 (contrato 03-contratos-api.md §6 / ADR-0002)
            for ev in events:
                assert set(ev) == ENVELOPE_V1
                assert isinstance(ev["seq"], int) and ev["seq"] >= 1
                assert isinstance(ev["timestamp"], str) and ev["timestamp"]

            # SÓ eventos daquele run
            assert all(ev["run_id"] == run_id for ev in events)

            # seq estritamente incremental (sem duplicatas, sem saltos para trás)
            seqs = [ev["seq"] for ev in events]
            assert seqs == sorted(seqs), f"seq fora de ordem: {seqs}"
            assert len(set(seqs)) == len(seqs), f"seq duplicado: {seqs}"

            # A3: task_id preservado DENTRO do payload
            assert all("task_id" in ev["payload"] for ev in events)

            # Um evento terminal veio por este canal
            assert any(ev["event"] in TERMINAL_EVENTS for ev in events)


def test_ws_streaming_global_receives_same_events():
    """/ws/streaming segue global: recebe os mesmos envelopes v1 (inclusive run_created)."""
    app = create_app()

    with TestClient(app) as tc:
        with tc.websocket_connect("/ws/streaming") as ws:
            first = ws.receive_json()
            assert first["event"] == "connected"

            resp = tc.post(
                "/api/runs",
                json={"idea": "WS global", "stack": "python", "mock_llm": True},
            )
            assert resp.status_code == 201
            run_id = resp.json()["id"]

            events = _collect_events(ws)
            assert events, "nenhum envelope v1 recebido no stream global"

            for ev in events:
                assert set(ev) == ENVELOPE_V1
                assert ev["run_id"] == run_id

            seqs = [ev["seq"] for ev in events]
            assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)

            # Conectado ANTES da criação → o stream global vê run_created
            assert any(ev["event"] == "run_created" for ev in events), (
                f"run_created ausente no stream global: {[e['event'] for e in events]}"
            )
            # Task_id preservado no payload dos eventos de pipeline (A3)
            pipeline_events = [
                ev for ev in events if ev["event"] in ("pipeline_started", "node_execution", "pipeline_finished")
            ]
            assert pipeline_events and all("task_id" in ev["payload"] for ev in pipeline_events)


def test_ws_run_channel_rejeita_token_invalido(monkeypatch):
    """Auth ligada: token errado em /ws/runs/{run_id} é rejeitado (1008)."""
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "true")
    monkeypatch.setenv("LF_API_API_KEY", "token-certo")
    app = create_app()

    with TestClient(app) as tc:
        with pytest.raises(Exception):
            with tc.websocket_connect("/ws/runs/abc?token=token-errado"):
                pass
