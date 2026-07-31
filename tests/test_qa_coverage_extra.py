from lf.pipeline.nodes import qa as qa_module


def test_qa_sem_codigo_envia_para_developer():
    state = {
        "code": "",
        "mock_llm": False,
        "feedback_history": [],
        "qa_attempt_count": 0,
        "max_retries": 3,
    }

    result = qa_module.qa(state)

    assert result["next_agent"] == "developer"
    assert result["qa_attempt_count"] == 1
    assert result["test_report"]["summary"]["status"] == "FAIL"
    assert result["feedback_history"][-1]["from"] == "qa"


def test_qa_fallback_quando_llm_retorna_invalido(monkeypatch, tmp_path):
    monkeypatch.setattr(
        qa_module,
        "_run_harness",
        lambda *_args, **_kwargs: {
            "success": True,
            "passed": 2,
            "failed": 0,
            "total": 2,
            "errors": [],
            "duration_ms": 50,
            "output": "ok",
        },
    )
    monkeypatch.setattr(qa_module, "call_llm_via_opencode", lambda **_kwargs: "")

    state = {
        "code": "print('ok')",
        "mock_llm": False,
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "feedback_history": [],
    }

    result = qa_module.qa(state)

    assert result["next_agent"] == "appsec"
    assert result["test_report"]["summary"]["status"] == "PASS"
    assert result["test_report"]["summary"]["tests_failed"] == 0


def test_qa_harness_falha_forca_fail_e_feedback(monkeypatch, tmp_path):
    monkeypatch.setattr(
        qa_module,
        "_run_harness",
        lambda *_args, **_kwargs: {
            "success": False,
            "passed": 0,
            "failed": 1,
            "total": 1,
            "errors": ["Falha de compilacao X"],
            "duration_ms": 10,
            "output": "compiler error details",
        },
    )
    monkeypatch.setattr(
        qa_module,
        "call_llm_via_opencode",
        lambda **_kwargs: {
            "summary": {"status": "PASS", "tests_failed": 0, "tests_passed": 1},
            "results_by_suite": [],
        },
    )

    state = {
        "code": "code",
        "mock_llm": False,
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "feedback_history": [],
        "qa_attempt_count": 0,
        "max_retries": 2,
    }

    result = qa_module.qa(state)

    assert result["next_agent"] == "developer"
    assert result["qa_attempt_count"] == 1
    assert result["test_report"]["summary"]["status"] == "FAIL"
    assert "FALHA NO QA" in result["feedback_history"][-1]["message"]


def test_qa_self_healing_reexecuta_harness(monkeypatch, tmp_path):
    calls = {"n": 0}

    def fake_run_harness(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {
                "success": False,
                "passed": 0,
                "failed": 1,
                "total": 1,
                "errors": ["dep mismatch"],
                "duration_ms": 1,
                "output": "erro",
            }
        return {
            "success": True,
            "passed": 1,
            "failed": 0,
            "total": 1,
            "errors": [],
            "duration_ms": 1,
            "output": "ok",
        }

    monkeypatch.setattr(qa_module, "_run_harness", fake_run_harness)
    monkeypatch.setattr(qa_module, "_attempt_dependency_self_healing", lambda *_a, **_k: True)
    monkeypatch.setattr(qa_module, "call_llm_via_opencode", lambda **_kwargs: {"summary": {"status": "PASS", "tests_failed": 0}})

    state = {
        "code": "code",
        "mock_llm": False,
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "feedback_history": [],
    }

    result = qa_module.qa(state)
    assert calls["n"] == 2
    assert result["next_agent"] == "appsec"
