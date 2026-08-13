"""Testes do estado incremental (milestone v7 5.1) — canais e should_retry.

Flag off → should_retry retorna exatamente os valores legados; flag on →
canais presentes e roteamento entre slices (test_writer/developer/parallel_audit).
"""

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.graph import should_retry


def _base_state() -> dict:
    return {
        "incremental_slices": False,
        "slices": [],
        "slice_index": 0,
        "slice_status": "",
        "slice_test_report": {},
        "test_scope": "full",
        "slice_max_retries": 3,
        "max_retries": 3,
        "qa_attempt_count": 0,
        "test_report": {},
    }


# ─── Flag off: comportamento byte-idêntico ao atual ─────────────────────────


def test_should_retry_off_passa_parallel_audit():
    state = _base_state()
    state["test_report"] = {"summary": {"tests_failed": 0}}
    assert should_retry(state) == "parallel_audit"


def test_should_retry_off_falha_com_retries_developer():
    state = _base_state()
    state["test_report"] = {"summary": {"tests_failed": 2}}
    state["qa_attempt_count"] = 1  # < max_retries
    assert should_retry(state) == "developer"


def test_should_retry_off_esgotado_parallel_audit():
    state = _base_state()
    state["test_report"] = {"summary": {"tests_failed": 2}}
    state["qa_attempt_count"] = 5  # >= max_retries
    assert should_retry(state) == "parallel_audit"


# ─── Flag on: roteamento incremental ────────────────────────────────────────


def _slice_state(slice_index: int, status: str, attempts: int = 0, n_slices: int = 2) -> dict:
    slices = [
        {
            "story": {"id": f"E-001-US00{i + 1}"},
            "status": "passed" if i < slice_index else "pending",
            "attempts": attempts if i == slice_index else 0,
            "test_report": {},
        }
        for i in range(n_slices)
    ]
    return {
        **_base_state(),
        "incremental_slices": True,
        "slices": slices,
        "slice_index": slice_index,
        "slice_status": status,
    }


def test_should_retry_on_slice_pass_avanca_test_writer():
    state = _slice_state(slice_index=0, status="passed")
    assert should_retry(state) == "test_writer"


def test_should_retry_on_ultimo_slice_pass_parallel_audit():
    state = _slice_state(slice_index=1, status="passed")
    assert should_retry(state) == "parallel_audit"


def test_should_retry_on_slice_fail_com_retries_developer():
    state = _slice_state(slice_index=0, status="failed", attempts=1)
    assert should_retry(state) == "developer"


def test_should_retry_on_slice_fail_esgotado_parallel_audit():
    state = _slice_state(slice_index=0, status="failed", attempts=4)  # >= slice_max_retries 3
    assert should_retry(state) == "parallel_audit"


# ─── Canais no estado inicial do dispatcher ─────────────────────────────────


def test_build_initial_state_canais_incrementais_presentes():
    dispatcher = TaskDispatcher(mock_llm=True)
    task = TaskSchema(id="slice-st-1", title="t", stack="python")
    state = dispatcher._build_initial_state(task, "proj-slice-st")
    assert state["incremental_slices"] is False
    assert state["slices"] == []
    assert state["slice_index"] == 0
    assert state["slice_status"] == ""
    assert state["slice_test_report"] == {}
    assert state["test_scope"] == "full"
    assert state["slice_max_retries"] == 3
