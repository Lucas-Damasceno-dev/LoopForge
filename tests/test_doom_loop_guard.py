"""Testes unitários para o Doom-Loop Guard e detecção de estagnação em retries."""

from lf.pipeline.graph import should_retry
from lf.pipeline.nodes.qa import compute_qa_fingerprint, qa
from lf.pipeline.pipeline_graph import _retry_router
from lf.pipeline.state import GraphState


def test_compute_qa_fingerprint_deterministic():
    code1 = "def add(a, b): return a + b"
    code2 = "def add(a, b): return a - b"
    report1 = {"summary": {"tests_failed": 1, "errors": ["AssertionError: 3 != 4"]}}
    report2 = {"summary": {"tests_failed": 1, "errors": ["AssertionError: 3 != 4"]}}

    fp1 = compute_qa_fingerprint(code1, report1)
    fp2 = compute_qa_fingerprint(code1, report2)
    fp3 = compute_qa_fingerprint(code2, report1)

    assert fp1 == fp2
    assert fp1 != fp3


def test_should_retry_aborts_on_doom_loop():
    # Estado com testes falhando e retries sobrando (1 de 3), mas doom_loop_detected=True
    state: GraphState = {
        "test_report": {"summary": {"tests_failed": 2}},
        "qa_attempt_count": 1,
        "max_retries": 3,
        "doom_loop_detected": True,
        "doom_loop_reason": "2 tentativas consecutivas idênticas",
    }  # type: ignore

    decision = should_retry(state)
    # Sem doom loop iria para "developer"; com doom loop vai direto para "parallel_audit"
    assert decision == "parallel_audit"


def test_pipeline_graph_retry_router_respects_doom_loop():
    router = _retry_router(max_retries=3, retry_target="dev_node", next_target="audit_node")

    # Caso normal com retries restantes -> dev_node
    normal_state: GraphState = {"attempt_count": 1, "doom_loop_detected": False}  # type: ignore
    assert router(normal_state) == "dev_node"

    # Caso com doom loop detectado -> audit_node
    doom_state: GraphState = {"attempt_count": 1, "doom_loop_detected": True}  # type: ignore
    assert router(doom_state) == "audit_node"
