"""Testes do HITL timeout gracioso: transição decision_expired + broadcast human_decision_expired."""
import asyncio

import pytest

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


@pytest.mark.asyncio
async def test_hitl_expiry_broadcasts_decision_expired(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    events = []
    monkeypatch.setattr(
        TaskDispatcher,
        "_broadcast_ws",
        lambda self, event, *a, **k: events.append((event, a, k)),
    )
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=0)
    # hitl_timeout_seconds=0 -> expira imediatamente na 1a pausa; transição graciosa
    task = TaskSchema(id="task-expiry-1", title="Build timeout feature", agent_id="cpo")
    result = await asyncio.to_thread(dispatcher.dispatch, task=task, project_id="proj-expiry")

    expired = [e for e in events if e[0] == "human_decision_expired"]
    assert expired, "human_decision_expired deve ser broadcastado no timeout"
    payload = expired[0][1][1]
    assert payload["timeout_seconds"] == 0
    assert payload.get("node")
    # Transição graciosa: pipeline NÃO aborta (segue em frente, sem erro)
    assert not result.get("error")
