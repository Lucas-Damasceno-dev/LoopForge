"""Onda 2 (2.2): propagação do retry do AppSec (appsec_attempt_count + feedback_history).

Cobre o bug em que parallel_audit montava um dict novo e descartava os campos de
retry do AppSec — o contador nunca acumulava (loop infinito) e o feedback de
segurança se perdia antes de chegar ao Developer.
"""

from lf.pipeline.graph import NodeRegistry, build_graph
from lf.pipeline.nodes.developer import developer as developer_node
from lf.pipeline.nodes.parallel_audit import parallel_audit
from lf.pipeline.nodes.qa import qa as qa_node


def _base_state() -> dict:
    return {
        "task_id": "task-1",
        "idea": "teste",
        "history": [],
        "next_agent": "parallel_audit",
    }


def test_parallel_audit_propaga_appsec_retry_para_developer(monkeypatch):
    """Node-level: updated_state deve propagar appsec_attempt_count e feedback_history."""

    def appsec_fail(_state):
        return {
            "next_agent": "developer",
            "appsec_attempt_count": 1,
            "feedback_history": [{"from": "appsec", "message": "APPSEC CRÍTICO: eval()"}],
        }

    def devops_ok(_state):
        return {"devops_report": {"status": "ok"}, "devops_manifest": {"pipeline": "ok"}}

    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.appsec", appsec_fail)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.devops", devops_ok)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.generate_lessons_md", lambda _state: None)

    result = parallel_audit(_base_state())

    assert result["next_agent"] == "developer"
    assert result["appsec_attempt_count"] == 1
    assert any("APPSEC CRÍTICO" in fb.get("message", "") for fb in result["feedback_history"])


def test_e2e_appsec_retry_chega_no_developer_com_feedback(monkeypatch):
    """E2E via build_graph: retry do AppSec volta ao Developer com o feedback APPSEC no estado."""
    seen = {}

    def fake_developer(state):
        fb = state.get("feedback_history", [])
        if state.get("next_agent") == "developer" and any("APPSEC CRÍTICO" in f.get("message", "") for f in fb):
            seen["appsec_retried"] = True
            return {**state, "next_agent": "FINISH"}
        return {**state, "code": "x", "next_agent": "qa"}

    def fake_qa(state):
        return {
            **state,
            "test_report": {"summary": {"tests_failed": 0, "tests_passed": 1}},
            "next_agent": "parallel_audit",
        }

    def fake_appsec(_state):
        return {
            "next_agent": "developer",
            "appsec_attempt_count": 1,
            "feedback_history": [{"from": "appsec", "message": "APPSEC CRÍTICO: eval()"}],
        }

    def fake_devops(_state):
        return {"devops_report": {"status": "ok"}, "devops_manifest": {"pipeline": "ok"}}

    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.appsec", fake_appsec)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.devops", fake_devops)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.generate_lessons_md", lambda _state: None)
    NodeRegistry.register("developer", fake_developer)
    NodeRegistry.register("qa", fake_qa)
    try:
        graph = build_graph()
        state = {
            "idea": "app",
            "next_agent": "developer",
            "mock_llm": True,
            "feedback_history": [],
            "appsec_attempt_count": 0,
        }
        result = graph.invoke(state)
        assert seen.get("appsec_retried") is True
        assert result["appsec_attempt_count"] == 1
        assert any("APPSEC CRÍTICO" in f.get("message", "") for f in result.get("feedback_history", []))
    finally:
        NodeRegistry.register("developer", developer_node)
        NodeRegistry.register("qa", qa_node)
