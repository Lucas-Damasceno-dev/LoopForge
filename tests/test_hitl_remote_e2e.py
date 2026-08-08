"""E2E HITL remoto (M-22/A9 da Fase A): decisão via POST /decide no gate, SEM stdin.

Cobre o bug vivo em que o dispatcher pollava `human_decisions` com
`run_id = thread_id` enquanto a API gravava `run_id = uuid` — a decisão nunca
casava e o gate dependia de input local. Aqui o dispatcher roda com input
simulado de "nenhuma tecla" (''), e a ÚNICA forma do gate avançar é o polling
pelo uuid extraído do thread `run-{uuid}` consumir a decisão do POST /decide.
"""

import asyncio
import sqlite3
import threading
import time
import uuid
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


@pytest_asyncio.fixture(autouse=True)
async def setup_hitl_env(tmp_path, monkeypatch):
    """Isola em tmp_path usando o MESMO banco da API e do dispatcher.

    IMPORTANTE: NÃO seta LF_API_TEST — sob LF_API_TEST a API escreveria em
    .loopforge/test_api.sqlite enquanto o dispatcher polla telemetry.sqlite.
    Em produção ambos usam o default sqlite+aiosqlite:///.loopforge/telemetry.sqlite.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LF_API_TEST", raising=False)
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


@pytest.mark.asyncio
async def test_hitl_remote_decision_consumed_at_gate():
    app = create_app()
    run_id = str(uuid.uuid4())
    task = TaskSchema(id=run_id, title="Build HITL remote feature", agent_id="cpo")
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=60)

    results: dict = {}

    def _run_dispatch():
        # Loop real do dispatcher (caminho síncrono HITL). project_id 'run-{uuid}'
        # vira a thread canônica `run-{uuid}` (ADR-0003/M-02).
        results["state"] = dispatcher.dispatch(task=task, project_id=f"run-{run_id}")

    # Nenhuma tecla local: simula operador ausente no gate. A decisão deve
    # chegar EXCLUSIVAMENTE pelo polling remoto do POST /decide.
    with patch.object(dispatcher, "_get_single_key_with_timeout", return_value=""):
        thread = threading.Thread(target=_run_dispatch, daemon=True)
        start = time.monotonic()
        thread.start()

        # Aguarda a pipeline alcançar o primeiro gate (developer -> qa). O gate
        # fica em polling de 0.5s por decisão remota até hitl_timeout_seconds.
        await asyncio.sleep(2.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            dec_resp = await client.post(
                f"/api/runs/{run_id}/decide",
                json={"gate_node": "developer", "action": "approve", "user": "e2e-tester"},
            )
            assert dec_resp.status_code == 201

        thread.join(timeout=120)
        elapsed = time.monotonic() - start

    assert not thread.is_alive(), "dispatcher travou no gate — decisão remota não foi consumida"
    assert "state" in results, "dispatch não retornou"
    assert not results["state"].get("error"), results["state"].get("error")
    # Gate avançou pela decisão remota, não por timeout-continue (60s por gate):
    assert elapsed < 60, f"pipeline levou {elapsed:.1f}s — suspeito de timeout-continue"

    # Prova da chave correta: o dispatcher gravou suas próprias decisões de gate
    # com run_id = uuid (a cada gate aprovado o polling casou com a chave da API).
    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM human_decisions WHERE run_id = ?", (run_id,)
        ).fetchone()[0]
    finally:
        conn.close()
    # 1 linha do POST /decide + registros do dispatcher nos gates aprovados
    assert count >= 2, f"esperado decisão da API + registros do dispatcher, achou {count}"
