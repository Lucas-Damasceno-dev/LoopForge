"""Suíte de testes para o auto-formatador do TestHarnessRunner."""
from unittest.mock import patch

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
