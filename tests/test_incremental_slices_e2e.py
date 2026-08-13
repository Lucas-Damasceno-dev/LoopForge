"""E2E mock do pipeline incremental (milestone v7 5.1) — 2 slices.

Fluxo esperado com 2 user stories e tudo mock:
  cpo → pm (reusa stories) → tech_lead → test_writer (slice 0) → developer
  (slice 0) → qa (passa) → should_retry: test_writer (slice 1) → developer
  (slice 1, slice_index avança) → qa (passa) → should_retry: parallel_audit (1x).

Asserts: slices todos "passed", slice_index == 1, parallel_audit executado
exatamente 1x, canais slice presentes no estado final.
"""

from unittest.mock import patch

import pytest_asyncio

from lf.api.database import close_db, init_db
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.graph import NodeRegistry

STORIES = [
    {
        "id": "E-001-US001",
        "title": "Funcionalidade principal",
        "epic_id": "E-001",
        "as_a": "usuário",
        "i_want_to": "realizar ação principal",
        "so_that": "obter valor",
        "acceptance_criteria": ["Dado que...", "Então..."],
        "priority": "High",
        "status": "Pending",
    },
    {
        "id": "E-001-US002",
        "title": "Relatório avançado",
        "epic_id": "E-001",
        "as_a": "gerente",
        "i_want_to": "ver relatório",
        "so_that": "decidir",
        "acceptance_criteria": ["Quando...", "Então..."],
        "priority": "Medium",
        "status": "Pending",
    },
]


@pytest_asyncio.fixture(autouse=True)
async def slice_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_WORKDIR_BASE", str(tmp_path / "workbase"))
    await init_db()
    yield
    await close_db()


def test_e2e_2_slices_mock(tmp_path):
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)
    task = TaskSchema(
        id="slice-e2e-1",
        title="Feature slices",
        agent_id="cpo",
        stack="python",
        incremental_slices=True,
    )

    # Espião no nó parallel_audit: conta execuções sem alterar o grafo.
    original_audit = NodeRegistry._nodes["parallel_audit"]
    audit_calls: list = []

    def _spy_audit(state):
        audit_calls.append(state)
        return original_audit(state)

    with patch.object(NodeRegistry, "_nodes", {**NodeRegistry._nodes, "parallel_audit": _spy_audit}):
        res = dispatcher.dispatch(task, project_id="proj-slice-e2e", shared_state={"user_stories": STORIES})

    assert not res.get("error"), res.get("error")
    # Canais slice presentes no estado final
    assert res.get("incremental_slices") is True
    assert res.get("slice_index") == 1  # último slice processado
    assert res.get("slice_status") == "passed"
    assert res.get("test_scope") == "slice"
    # Os 2 slices foram implementados e aprovados
    slices = res.get("slices", [])
    assert len(slices) == 2
    assert [s["status"] for s in slices] == ["passed", "passed"]
    assert all(s["attempts"] >= 1 for s in slices)
    assert all(s.get("test_report", {}).get("slice_failed") == 0 for s in slices)
    # Auditoria final executada EXATAMENTE 1x (só no fim dos slices)
    assert len(audit_calls) == 1, f"parallel_audit deveria rodar 1x, rodou {len(audit_calls)}"
