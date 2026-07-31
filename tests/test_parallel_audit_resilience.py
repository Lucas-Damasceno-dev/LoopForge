from lf.pipeline.nodes.parallel_audit import parallel_audit


def _base_state() -> dict:
    return {
        "task_id": "task-1",
        "idea": "teste",
        "history": [],
        "next_agent": "parallel_audit",
    }


def test_parallel_audit_resiliente_quando_appsec_falha(monkeypatch):
    def appsec_fail(_state):
        raise RuntimeError("erro appsec")

    def devops_ok(_state):
        return {
            "devops_report": {"status": "ok"},
            "devops_manifest": {"pipeline": "ok"},
        }

    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.appsec", appsec_fail)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.devops", devops_ok)
    monkeypatch.setattr("lf.pipeline.nodes.parallel_audit.generate_lessons_md", lambda _state: None)

    result = parallel_audit(_base_state())

    assert result["devops_report"] == {"status": "ok"}
    assert result["devops_manifest"] == {"pipeline": "ok"}
    assert "appsec falhou" in (result.get("error") or "")
    assert result["next_agent"] == "FINISH"

