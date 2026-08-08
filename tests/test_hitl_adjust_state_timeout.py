"""Testes C3+C4 da Fase C da ADE no LoopForge.

C3 (M-12) adjust_state:
  (a) E2E: dispatcher em gate, POST /decide com state_patch → run prossegue e
      o checkpoint reflete o patch (canais reais do GraphState);
  (b) state_patch inválido (não-dict) → 422 com mensagem PT.

C4 (M-11) hitl.on_timeout:
  (c) abort: gate expira → run falha com motivo 'hitl_timeout_abort' e nenhum
      nó pós-gate executa (sem consumo de LLM);
  (d) pause: expira → gate permanece aberto, decisão tardia é aceita e a run
      completa (sem human_decision_expired);
  (e) hitl_gate_reached publicado no primeiro gate com payload correto
      (gate_node, thread_id, run_id resolvido, timeout_seconds, on_timeout, ts);
  (f) GET /api/v1/config expõe hitl.on_timeout.

Padrões endurecidos: chdir(tmp_path) hermético; SEM LF_API_TEST em testes que
exigem a API e o dispatcher compartilhando .loopforge/telemetry.sqlite (mesmo
padrão de test_hitl_remote_e2e); limpeza de WAL/SHM órfãos.
"""

import asyncio
import contextlib
import os
import threading
import time
import uuid
from pathlib import Path
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
    """Isola em tmp_path SEM LF_API_TEST (padrão de test_hitl_remote_e2e).

    A API e o dispatcher compartilham .loopforge/telemetry.sqlite — necessário
    para o polling do gate (human_decisions) casar com o POST /decide.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LF_API_TEST", raising=False)
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    monkeypatch.setenv("OPENCODE_MOCK", "1")
    await init_db()
    yield
    await close_db()
    # Garante que nenhum WAL órfão polua o próximo teste da suíte.
    for f in (".loopforge/telemetry.sqlite-wal", ".loopforge/telemetry.sqlite-shm"):
        with contextlib.suppress(Exception):
            os.remove(f)


async def _final_state(thread_id: str) -> dict:
    """Estado final do checkpoint da thread (via AsyncSqliteSaver)."""
    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return dict(snap.values) if snap else {}
    finally:
        await saver.conn.close()


# ─── C3 (M-12): adjust_state ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_adjust_state_e2e_aplica_patch_e_run_prossegue():
    """(a) POST /decide com action=adjust_state + state_patch no gate.

    O dispatcher em polling consome a decisão, aplica o patch ao checkpoint e a
    run prossegue — o estado final reflete os canais reais patchados (idea e
    routing_mode) e o campo arbitrário é descartado pelo LangGraph.
    """
    app = create_app()
    run_id = str(uuid.uuid4())
    task = TaskSchema(id=run_id, title="Ajustar estado via HITL", agent_id="cpo")
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=60)

    results: dict = {}

    def _run_dispatch():
        results["state"] = dispatcher.dispatch(task=task, project_id=f"run-{run_id}")

    patch_payload = {
        "idea": "ideia ajustada via adjust_state",
        "routing_mode": "patch",
        "campo_arbitrario": {"nao": "é canal do GraphState"},
    }
    with patch.object(dispatcher, "_get_single_key_with_timeout", return_value=""):
        thread = threading.Thread(target=_run_dispatch, daemon=True)
        start = time.monotonic()
        thread.start()

        # Aguarda a pipeline alcançar o primeiro gate (developer -> qa).
        await asyncio.sleep(2.0)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            resp = await client.post(
                f"/api/runs/{run_id}/decide",
                json={
                    "gate_node": "developer",
                    "action": "adjust_state",
                    "state_patch": patch_payload,
                    "user": "e2e",
                },
            )
            assert resp.status_code == 201

        thread.join(timeout=120)
        elapsed = time.monotonic() - start

    assert not thread.is_alive(), "dispatcher travou no gate — decisão adjust_state não foi consumida"
    assert not results["state"].get("error"), results["state"].get("error")
    assert elapsed < 60, f"gate deveria avançar pela decisão remota, não por timeout: {elapsed:.1f}s"

    # Checkpoint final reflete o patch nos canais reais do GraphState
    final = await _final_state(f"run-{run_id}")
    assert final.get("idea") == "ideia ajustada via adjust_state"
    assert final.get("routing_mode") == "patch"
    # Canal fora do TypedDict é descartado pelo LangGraph (documentado)
    assert "campo_arbitrario" not in final

    # A decisão foi persistida com o state_patch serializado (audit trail)
    import sqlite3

    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        row = conn.execute(
            "SELECT action, state_patch FROM human_decisions WHERE run_id = ? "
            "AND action = 'adjust_state' ORDER BY timestamp DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "decisão adjust_state deveria estar em human_decisions"
    assert "ideia ajustada via adjust_state" in row[1]


@pytest.mark.asyncio
async def test_adjust_state_patch_invalido_422():
    """(b) state_patch não-dict → 422 com mensagem PT (field_validator)."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        resp = await client.post(
            f"/api/runs/{uuid.uuid4()}/decide",
            json={"gate_node": "developer", "action": "adjust_state", "state_patch": "nao-sou-dict"},
        )
        assert resp.status_code == 422
        detail = str(resp.json()["detail"])
        assert "state_patch" in detail
        assert "deve ser um objeto JSON" in detail


# ─── C4 (M-11): hitl.on_timeout ─────────────────────────────────────────────


def test_hitl_on_timeout_abort_falha_sem_llm(tmp_path, monkeypatch):
    """(c) on_timeout=abort: gate expira → run failed com motivo, sem LLM.

    Com hitl_timeout_seconds=0 o primeiro gate (após developer) expira na hora:
    a run aborta SEM re-agendar nós — nenhum nó pós-gate (qa/parallel_audit)
    executa, provando que não há consumo de LLM após o aborto.
    """
    monkeypatch.chdir(tmp_path)
    events = []
    monkeypatch.setattr(
        TaskDispatcher,
        "_broadcast_ws",
        lambda self, event, *a, **k: events.append((event, a, k)),
    )
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=0, hitl_on_timeout="abort")
    task = TaskSchema(id="task-abort-1", title="Abort no timeout", agent_id="cpo")
    result = dispatcher.dispatch(task=task, project_id="proj-abort")

    # Run falha controladamente (estado final marcado como failed)
    assert result.get("error"), "on_timeout=abort deveria marcar a run como failed"
    assert "abortado" in result["error"]

    # pipeline_failed com motivo hitl_timeout_abort
    failed = [e for e in events if e[0] == "pipeline_failed" and e[1][1].get("motivo") == "hitl_timeout_abort"]
    assert failed, "pipeline_failed com motivo=hitl_timeout_abort deveria ser broadcast"
    assert failed[0][1][1]["run_status"] == "failed"

    # Sem consumo de LLM pós-gate: qa/parallel_audit nunca executaram
    executed = {e[1][1].get("node") for e in events if e[0] == "node_execution"}
    assert "qa" not in executed, f"qa não deveria executar após abort: {executed}"
    assert "parallel_audit" not in executed


def test_hitl_on_timeout_pause_aguarda_decisao_tardia(tmp_path, monkeypatch):
    """(d) on_timeout=pause: expira → gate aberto, decisão tardia aceita.

    A decisão chega DEPOIS do timeout (1s). Em pause o gate continua aguardando,
    a decisão tardia é consumida e a run completa — e NENHUM human_decision_expired
    é emitido (a semântica continue/expiry não se aplica).
    """
    monkeypatch.chdir(tmp_path)
    events = []
    monkeypatch.setattr(
        TaskDispatcher,
        "_broadcast_ws",
        lambda self, event, *a, **k: events.append((event, a, k)),
    )
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=1, hitl_on_timeout="pause")
    run_id = str(uuid.uuid4())
    task = TaskSchema(id=run_id, title="Pause no timeout", agent_id="cpo")

    results: dict = {}

    def _run_dispatch():
        results["state"] = dispatcher.dispatch(task=task, project_id=f"run-{run_id}")

    with patch.object(dispatcher, "_get_single_key_with_timeout", return_value=""):
        thread = threading.Thread(target=_run_dispatch, daemon=True)
        start = time.monotonic()
        thread.start()

        # Espera o timeout expirar (1s) + margem; SEM decisão ainda, o pause
        # deve manter o gate aberto (thread viva, run incompleta).
        time.sleep(2.0)
        assert thread.is_alive(), "on_timeout=pause deveria manter o gate aberto após o timeout (sem decisão)"

        # Decisão TARDIA: chega depois do deadline — em pause ela é aceita.
        dispatcher._record_decision(run_id, "developer", "approve")

        thread.join(timeout=120)
        elapsed = time.monotonic() - start

    assert not thread.is_alive(), "dispatcher travou — decisão tardia não foi aceita no pause"
    assert not results["state"].get("error"), results["state"].get("error")
    # A run esperou além do timeout (1s) e ainda assim completou
    assert elapsed >= 1.5, f"pause deveria aguardar além do timeout: {elapsed:.1f}s"
    # pause NÃO emite human_decision_expired (semântica exclusiva do continue)
    expired = [e for e in events if e[0] == "human_decision_expired"]
    assert not expired, "on_timeout=pause não deveria emitir human_decision_expired"


def test_hitl_gate_reached_payload_correto(tmp_path, monkeypatch):
    """(e) Evento hitl_gate_reached publicado na primeira entrada do gate.

    Payload {gate_node, thread_id, run_id (uuid resolvido), timeout_seconds,
    on_timeout, ts}; não duplicado para o mesmo (run, nó).
    """
    monkeypatch.chdir(tmp_path)
    events = []
    monkeypatch.setattr(
        TaskDispatcher,
        "_broadcast_ws",
        lambda self, event, *a, **k: events.append((event, a, k)),
    )
    run_id = str(uuid.uuid4())
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=0, hitl_on_timeout="abort")
    task = TaskSchema(id=run_id, title="Gate reached", agent_id="cpo")
    dispatcher.dispatch(task=task, project_id=f"run-{run_id}")

    reached = [e for e in events if e[0] == "hitl_gate_reached"]
    assert reached, "hitl_gate_reached deveria ser publicado no primeiro gate"
    assert len(reached) == 1, f"hitl_gate_reached não deveria duplicar: {len(reached)}"

    payload = reached[0][1][1]
    assert payload["gate_node"] == "qa"  # primeiro gate: após developer
    assert payload["thread_id"] == f"run-{run_id}"
    # run_id é o uuid resolvido do thread `run-{uuid}` (ADR-0003/M-22)
    assert payload["run_id"] == run_id
    assert payload["timeout_seconds"] == 0
    assert payload["on_timeout"] == "abort"
    assert payload["ts"]


@pytest.mark.asyncio
async def test_config_expoe_hitl_on_timeout(tmp_path, monkeypatch):
    """(f) GET /api/v1/config expõe hitl.on_timeout (default continue)."""
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.get("/api/v1/config")
        assert r.status_code == 200
        hitl = r.json()["hitl"]
        assert hitl["timeout_seconds"] == 300
        assert hitl["on_timeout"] == "continue"

        # PATCH aceita e persiste on_timeout
        p = await ac.patch("/api/v1/config", json={"hitl": {"timeout_seconds": 30, "on_timeout": "pause"}})
        assert p.status_code == 200
        assert p.json()["hitl"]["on_timeout"] == "pause"
