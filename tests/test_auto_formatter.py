"""Suíte de testes para o auto-formatador do TestHarnessRunner."""

from unittest.mock import patch

from lf.pipeline.nodes import qa as qa_module
from lf.runner.harness.runner import TestHarnessRunner


def test_run_auto_formatter_python_ruff(tmp_path):
    runner = TestHarnessRunner(command="pytest", stack="python")

    with patch("shutil.which", return_value="/usr/bin/ruff"), patch("subprocess.run") as mock_run:
        runner.run_auto_formatter(tmp_path)
        mock_run.assert_called_once()
        assert "ruff format" in mock_run.call_args[0][0]


def test_run_auto_formatter_rust_cargo(tmp_path):
    runner = TestHarnessRunner(command="cargo test", stack="rust")

    with patch("shutil.which", return_value="/usr/bin/cargo"), patch("subprocess.run") as mock_run:
        runner.run_auto_formatter(tmp_path)
        mock_run.assert_called_once()
        assert "cargo fmt" in mock_run.call_args[0][0]


def test_run_auto_formatter_handles_exceptions_gracefully(tmp_path):
    runner = TestHarnessRunner(command="pytest", stack="python")

    mock_err = Exception("Subprocess error")
    with patch("shutil.which", return_value="/usr/bin/ruff"), patch("subprocess.run", side_effect=mock_err):
        # Deve capturar e logar sem lançar exceção
        runner.run_auto_formatter(tmp_path)


def test_run_executes_auto_formatter_when_enabled(tmp_path):
    runner = TestHarnessRunner(command="pytest", stack="python", auto_format=True)

    with patch.object(runner, "run_auto_formatter") as mock_formatter, patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed in 0.01s"
        mock_run.return_value.stderr = ""

        runner.run(tmp_path)

        mock_formatter.assert_called_once_with(tmp_path)


def test_run_does_not_execute_auto_formatter_by_default(tmp_path):
    runner = TestHarnessRunner(command="pytest", stack="python")

    with patch.object(runner, "run_auto_formatter") as mock_formatter, patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "1 passed in 0.01s"
        mock_run.return_value.stderr = ""

        runner.run(tmp_path)

        mock_formatter.assert_not_called()


def test_qa_harness_ativa_auto_formatter(tmp_path):
    """Onda 2 (2.1): o QA deve construir o TestHarnessRunner com auto_format=True."""
    fake_result = {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "output": "1 passed in 0.01s",
        "success": True,
        "command": "pytest",
        "command_missing": False,
        "errors": [],
    }
    with patch("lf.runner.harness.runner.TestHarnessRunner") as mock_cls:
        mock_cls.return_value.run.return_value = fake_result
        result = qa_module._run_harness(str(tmp_path), stack="python", output_dir=str(tmp_path))
        mock_cls.assert_called_once_with(stack="python", auto_format=True)
        assert result["passed"] == 1
