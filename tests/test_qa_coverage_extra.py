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


def test_qa_relatorio_direto_do_harness(monkeypatch, tmp_path):
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

    state = {
        "code": "print('ok')",
        "mock_llm": False,
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "feedback_history": [],
    }

    result = qa_module.qa(state)

    assert result["next_agent"] == "parallel_audit"
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

    state = {
        "code": "code",
        "mock_llm": False,
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "feedback_history": [],
    }

    result = qa_module.qa(state)
    assert calls["n"] == 2
    assert result["next_agent"] == "parallel_audit"


def test_run_harness_prefers_output_dir(monkeypatch, tmp_path):
    """C4: _run_harness roda no output_dir quando ele existe, não no project_dir."""

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, target_dir):
            captured["target_dir"] = target_dir
            from lf.runner.harness.runner import TestHarnessResult

            return TestHarnessResult(total=1, passed=1, failed=0, output="ok", success=True)

        def run_format_check(self, target_dir):
            return []

    captured = {}
    project_dir = tmp_path / "project"
    output_dir = tmp_path / "runs" / "proj-001"
    project_dir.mkdir()
    output_dir.mkdir(parents=True)

    monkeypatch.setattr("lf.runner.harness.runner.TestHarnessRunner", FakeRunner)
    qa_module._run_harness(str(project_dir), stack="python", output_dir=str(output_dir))
    assert captured["target_dir"] == str(output_dir)


def test_run_harness_falls_back_to_project_dir(monkeypatch, tmp_path):
    """C4: sem output_dir existente, _run_harness cai no project_dir."""

    class FakeRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, target_dir):
            captured["target_dir"] = target_dir
            from lf.runner.harness.runner import TestHarnessResult

            return TestHarnessResult(total=1, passed=1, failed=0, output="ok", success=True)

        def run_format_check(self, target_dir):
            return []

    captured = {}
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    missing_output = tmp_path / "runs" / "nao-existe"

    monkeypatch.setattr("lf.runner.harness.runner.TestHarnessRunner", FakeRunner)
    qa_module._run_harness(str(project_dir), stack="python", output_dir=str(missing_output))
    assert captured["target_dir"] == str(project_dir)


def test_qa_report_command_missing_message(monkeypatch, tmp_path):
    """C4: command_missing → erro 'comando de teste não encontrado', não 'Nenhum teste foi coletado'."""
    monkeypatch.setattr(
        qa_module,
        "_run_harness",
        lambda *_args, **_kwargs: {
            "success": False,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "errors": [],
            "duration_ms": 10,
            "output": "pytest: command not found",
            "command": "pytest",
            "command_missing": True,
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
        "user_stories": [],
    }

    result = qa_module.qa(state)
    assert result["next_agent"] == "developer"
    report = result["test_report"]
    assert report["summary"]["status"] == "FAIL"
    detail_error = report["results_by_suite"][0]["failed_tests_details"][0]["error"]
    assert "comando de teste não encontrado" in detail_error
    assert "Nenhum teste foi coletado" not in detail_error
