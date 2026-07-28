from unittest.mock import patch

from lf.orchestrator.plan_creator import create_plan_from_epic
from lf.pipeline.nodes.developer import _extract_generated_code, developer
from lf.pipeline.nodes.qa import _mock_report, qa
from lf.runner.opencode.models import OpenCodeResult


def test_extract_generated_code(tmp_path):
    # Test file extraction from changed_files
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    sample_code = dir1 / "app.py"
    sample_code.write_text("print('extracted')", encoding="utf-8")

    res = OpenCodeResult(exit_code=0, stdout="out", stderr="", changed_files=[str(sample_code)])
    extracted = _extract_generated_code(res, str(dir1), 0.0)
    assert "extracted" in extracted

    # Test markdown block extraction from stdout fallback
    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    res_md = OpenCodeResult(exit_code=0, stdout="```python\nprint('md')\n```", stderr="", changed_files=[])
    assert _extract_generated_code(res_md, str(dir2), 0.0) == "print('md')"

    # Test raw stdout fallback
    dir3 = tmp_path / "dir3"
    dir3.mkdir()
    res_raw = OpenCodeResult(exit_code=0, stdout="raw code stdout", stderr="", changed_files=[])
    assert _extract_generated_code(res_raw, str(dir3), 0.0) == "raw code stdout"



def test_developer_node_llm_execution(tmp_path):
    state = {
        "tech_spec": "# Spec\nImplement code",
        "user_stories": [{"id": "US-001", "title": "Implement feature", "description": "Desc"}],
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "mock_llm": False,
        "feedback_history": [{"from": "qa", "message": "Failed test"}],
    }

    mock_res = OpenCodeResult(
        exit_code=0,
        stdout="```python\ndef main():\n    pass\n```",
        stderr="",
        changed_files=[],
    )

    with patch("lf.pipeline.nodes.developer.OpenCodeRunner") as mock_runner_cls:
        instance = mock_runner_cls.return_value
        instance.run.return_value = mock_res

        res = developer(state)
        assert res["next_agent"] == "qa"
        assert "main" in res["code"]


def test_qa_node_llm_execution(tmp_path):
    state = {
        "code": "def add(a, b):\n    return a + b",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": False,
    }

    mock_harness_res = {"passed": 1, "total": 1, "errors": [], "duration_ms": 100}
    with patch("lf.pipeline.nodes.qa._run_harness", return_value=mock_harness_res):
        with patch("lf.pipeline.nodes.qa.call_llm_via_opencode") as mock_llm:
            mock_llm.return_value = _mock_report("EXEC-123", "2026-07-28")
            res = qa(state)
            assert res["next_agent"] == "appsec"
            assert res["test_report"]["summary"]["tests_passed"] == 10




def test_create_plan_from_epic(tmp_path):
    epic = {"id": "E-001", "title": "Sample Epic"}
    plan = create_plan_from_epic(epic, output_dir=str(tmp_path))
    assert len(plan.tasks) == 4
    assert plan.tasks[0]["persona"] == "pm"
