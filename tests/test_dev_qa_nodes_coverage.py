from unittest.mock import patch

from lf.orchestrator.plan_creator import create_plan_from_epic
from lf.pipeline.nodes.developer import (
    _extract_generated_code,
    _parse_multi_file_response,
    developer,
)
from lf.pipeline.nodes.qa import qa
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
    manifest_map = {
        "java": "pom.xml",
        "python": "pyproject.toml",
        "javascript": "package.json",
        "go": "go.mod",
        "rust": "Cargo.toml",
    }
    for stack, expected_manifest in manifest_map.items():
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

        manifest_path = target_dir / expected_manifest
        assert manifest_path.exists(), f"Manifest {expected_manifest} not created for {stack}"


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


def test_qa_node_harness_execution(tmp_path):
    state = {
        "code": "def add(a, b):\n    return a + b",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": False,
    }

    mock_harness_res = {"passed": 1, "total": 1, "failed": 0, "success": True, "errors": [], "duration_ms": 100}
    with patch("lf.pipeline.nodes.qa._run_harness", return_value=mock_harness_res):
        res = qa(state)
        assert res["next_agent"] == "parallel_audit"
        assert res["test_report"]["summary"]["tests_passed"] == 1


def test_create_plan_from_epic(tmp_path):
    epic = {"id": "E-001", "title": "Sample Epic"}
    plan = create_plan_from_epic(epic, output_dir=str(tmp_path))
    assert len(plan.tasks) == 4
    assert plan.tasks[0]["persona"] == "pm"


def test_developer_llm_error_aborts_with_finish(tmp_path):
    """C2: erro de LLM no Developer → next_agent == 'FINISH' (não segue para QA com código vazio)."""
    state = {
        "idea": "Calc app",
        "tech_spec": "# Spec\nImplement code",
        "user_stories": [{"id": "US-001", "title": "Implement feature", "acceptance_criteria": ["c1"]}],
        "project_dir": str(tmp_path),
        "output_dir": str(tmp_path),
        "mock_llm": False,
        "feedback_history": [],
        "attempt_count": 1,
    }

    with patch(
        "lf.pipeline.nodes.developer.call_llm_via_opencode",
        side_effect=RuntimeError("LLM Engine falhou: resposta contém erro de modelo/servidor"),
    ):
        res = developer(state)
        assert res["next_agent"] == "FINISH"
        assert res["code"] == ""
        assert "LLM Engine falhou" in res["error"]
        assert res["feedback_history"][-1]["from"] == "developer"
