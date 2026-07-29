from unittest.mock import patch

from lf.orchestrator.plan_creator import create_plan_from_epic
from lf.pipeline.nodes.developer import (
    STACK_PROJECT_TEMPLATES,
    _extract_generated_code,
    _parse_multi_file_response,
    developer,
)
from lf.pipeline.nodes.qa import _mock_report, qa
from lf.runner.opencode.models import OpenCodeResult


def test_extract_generated_code(tmp_path):
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    sample_code = dir1 / "app.py"
    sample_code.write_text("print('extracted')", encoding="utf-8")

    res = OpenCodeResult(exit_code=0, stdout="out", stderr="", changed_files=[str(sample_code)])
    extracted = _extract_generated_code(res, str(dir1), 0.0)
    assert "extracted" in extracted

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    res_md = OpenCodeResult(exit_code=0, stdout="```python\nprint('md')\n```", stderr="", changed_files=[])
    assert _extract_generated_code(res_md, str(dir2), 0.0) == "print('md')"

    dir3 = tmp_path / "dir3"
    dir3.mkdir()
    res_raw = OpenCodeResult(exit_code=0, stdout="raw code stdout", stderr="", changed_files=[])
    assert _extract_generated_code(res_raw, str(dir3), 0.0) == "raw code stdout"


def test_parse_multi_file_response():
    raw = """
### FILE: pom.xml
```xml
<project></project>
```

### FILE: src/main/java/Main.java
```java
public class Main {}
```
"""
    parsed = _parse_multi_file_response(raw, "default.java")
    assert "pom.xml" in parsed
    assert "<project></project>" in parsed["pom.xml"]
    assert "src/main/java/Main.java" in parsed


def test_developer_multi_file_mock_all_stacks(tmp_path):
    for stack in ("java", "python", "javascript", "go", "rust"):
        target_dir = tmp_path / stack
        state = {
            "idea": f"Test {stack} multi file app",
            "stack": stack,
            "mock_llm": True,
            "output_dir": str(target_dir),
            "project_dir": str(target_dir),
        }
        res = developer(state)
        assert res["next_agent"] == "qa"
        assert res["code"] is not None

        sc = STACK_PROJECT_TEMPLATES[stack]
        manifest_path = target_dir / sc["manifest_file"]
        test_path = target_dir / sc["test_file"]

        assert manifest_path.exists(), f"Manifest {sc['manifest_file']} not created for {stack}"
        assert test_path.exists(), f"Test file {sc['test_file']} not created for {stack}"


def test_developer_node_llm_execution(tmp_path):
    state = {
        "tech_spec": "# Spec\nImplement code",
        "user_stories": [{"id": "US-001", "title": "Implement feature", "description": "Desc"}],
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "mock_llm": False,
        "feedback_history": [{"from": "qa", "message": "Failed test"}],
    }

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode") as mock_call:
        mock_call.return_value = "```python\ndef main():\n    pass\n```"
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
