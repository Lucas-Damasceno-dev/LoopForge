import os
import subprocess
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

    markdown_json = '```json\n{"name": "test", "score": 10}\n```'
    assert _extract_json_from_text(markdown_json) == {"name": "test", "score": 10}

    text_wrapped = 'Here is the output:\n{"name": "test", "score": 10}\nDone!'
    assert _extract_json_from_text(text_wrapped) == {"name": "test", "score": 10}

    invalid = "Not json text"
    assert _extract_json_from_text(invalid) is None


# ─── C3: opencode runner — cwd do subprocesso aponta para o dir da run ──
def test_opencode_runner_subprocess_uses_run_dir(tmp_path):
    """O subprocesso deve rodar com cwd=run_dir, comando com --dir e env PWD no dir da run."""
    run_dir = tmp_path / "runs" / "proj-001"
    with patch("shutil.which", return_value="/usr/bin/opencode"), patch.dict(os.environ, {"OPENCODE_MOCK": "0"}):
        with patch("lf.runner.opencode.runner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="opencode output", stderr=""
            )
            runner = OpenCodeRunner(timeout_seconds=10)
            res = runner.run("create app", project_root=run_dir)
            assert res.success is True
            # C3: dir da run criado (cwd do subprocess precisa existir)
            assert run_dir.is_dir()

            call_args = mock_run.call_args
            assert call_args.kwargs["cwd"] == run_dir.resolve()
            # C3: --dir presente no comando do script -c
            cmd_str = " ".join(call_args.args[0])
            assert "--dir" in cmd_str
            assert str(run_dir.resolve()) in cmd_str
            # C3: PWD no env do subprocess
            assert call_args.kwargs["env"]["PWD"] == str(run_dir.resolve())


# ─── C4: harness — command_missing + PATH venv + PYTHONPATH ──────────────
def test_harness_command_missing_flag(tmp_path):
    """returncode 127 + 'command not found' → command_missing=True e stderr preservada."""
    with patch("lf.runner.harness.runner.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=127, stdout="", stderr="/bin/sh: pytest: command not found"
        )
        runner = TestHarnessRunner(command="pytest")
        res = runner.run(cwd=tmp_path)
        assert res.command_missing is True
        assert res.success is False
        assert res.total == 0
        assert "command not found" in res.output  # stderr original preservada


def test_harness_venv_pythonpath_env(tmp_path):
    """PATH ganha .venv/bin (subindo de cwd) e PYTHONPATH ganha cwd + cwd/src."""
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "src").mkdir()
    with patch("lf.runner.harness.runner.subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed in 0.01s", stderr=""
        )
        runner = TestHarnessRunner(command="pytest", stack="python")
        res = runner.run(cwd=tmp_path)
        assert res.success is True

        env = mock_run.call_args.kwargs["env"]
        assert str((tmp_path / ".venv" / "bin").resolve()) in env["PATH"].split(os.pathsep)
        py_parts = env["PYTHONPATH"].split(os.pathsep)
        assert str(tmp_path.resolve()) in py_parts
        assert str((tmp_path / "src").resolve()) in py_parts
