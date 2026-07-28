import time
from unittest.mock import MagicMock, patch

from pydantic import BaseModel, Field

from lf.runner.harness.runner import TestHarnessRunner
from lf.runner.opencode.llm import (
    _extract_json_from_text,
    call_llm_via_opencode,
)
from lf.runner.opencode.runner import OpenCodeRunner, detect_changed_files


class SampleModel(BaseModel):
    name: str = Field(..., description="Sample name")
    score: int = Field(0, description="Sample score")


def test_test_harness_runner(tmp_path):
    runner = TestHarnessRunner(command="echo '1 passed in 0.01s'")
    res = runner.run(cwd=tmp_path)
    assert res.total == 1
    assert res.passed == 1
    assert res.success is True

    # Test error handling
    bad_runner = TestHarnessRunner(command="non_existent_command_xyz_123")
    res_err = bad_runner.run(cwd=tmp_path)
    assert res_err.success is False
    assert res_err.total == 0



def test_opencode_runner_mock(tmp_path):
    with patch.dict("os.environ", {"OPENCODE_MOCK": "1"}):
        runner = OpenCodeRunner(timeout_seconds=10)
        result = runner.run("Create sample file", project_root=tmp_path)
        assert result.exit_code == 0
        assert "[MOCK OPENCODE]" in result.stdout


def test_opencode_runner_circuit_breaker(tmp_path):
    mock_cb = MagicMock()
    mock_cb.can_proceed.return_value = False

    runner = OpenCodeRunner(timeout_seconds=10)
    result = runner.run("Create sample file", project_root=tmp_path, circuit_breaker=mock_cb)
    assert result.exit_code == 1
    assert "Circuit breaker is open" in result.stderr


def test_detect_changed_files(tmp_path):
    start_time = time.time()
    sample_file = tmp_path / "sample.py"
    sample_file.write_text("print('hello')", encoding="utf-8")

    changed = detect_changed_files(tmp_path, start_time)
    assert str(sample_file) in changed


def test_call_llm_via_opencode_mock():
    res = call_llm_via_opencode(
        system_prompt="System prompt",
        user_prompt="User prompt",
        mock=True,
    )
    assert "[MOCK]" in res

    res_schema = call_llm_via_opencode(
        system_prompt="System prompt",
        user_prompt="User prompt",
        schema_model=SampleModel,
        mock=True,
    )
    assert isinstance(res_schema, dict)
    assert "name" in res_schema


def test_extract_json_from_text():
    raw_json = '{"name": "test", "score": 10}'
    assert _extract_json_from_text(raw_json) == {"name": "test", "score": 10}

    markdown_json = "```json\n{\"name\": \"test\", \"score\": 10}\n```"
    assert _extract_json_from_text(markdown_json) == {"name": "test", "score": 10}

    text_wrapped = "Here is the output:\n{\"name\": \"test\", \"score\": 10}\nDone!"
    assert _extract_json_from_text(text_wrapped) == {"name": "test", "score": 10}

    invalid = "Not json text"
    assert _extract_json_from_text(invalid) is None
