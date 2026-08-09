"""Testes do gate de erro de LLM (C2) e propagação de project_root (C3).

O wrapper `script` mascara o exit code do subprocesso opencode (success=True
mesmo quando o modelo é inválido), então o texto "Model not found"/"UnknownError"
chegava como resposta válida. O gate checa os marcadores de erro no TEXTO da
resposta e levanta RuntimeError mesmo com result.success == True.
"""

from unittest.mock import MagicMock, patch

import pytest

from lf.runner.opencode.llm import _raise_if_llm_error_marker, call_llm_via_opencode
from lf.runner.opencode.models import OpenCodeResult


def test_gate_raises_on_model_not_found_in_stdout_with_success_true():
    """success=True + stdout com 'Model not found' DEVE levantar RuntimeError (bug C2)."""
    with patch.dict(
        "os.environ",
        {"OPENROUTER_API_KEY": "", "OPENCODE_MODEL": "oc/deepseek-v4-flash-free"},
        clear=True,
    ):
        with patch("lf.runner.opencode.llm.OpenCodeRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = OpenCodeResult(
                exit_code=0,  # ← o bug: exit code mascarado como sucesso
                stdout="Model not found: deepseek-v4-flash-free",
                stderr="",
            )
            mock_runner_cls.return_value = mock_runner

            with pytest.raises(RuntimeError) as exc_info:
                call_llm_via_opencode(system_prompt="sys", user_prompt="usr", cache=False, mock=False)

            assert "LLM Engine falhou" in str(exc_info.value)
            assert "Model not found" in str(exc_info.value)


def test_gate_raises_on_openrouter_direct_error_text():
    """Path OpenRouter direto: texto de erro de modelo vira RuntimeError."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-test-key"}, clear=True):
        with patch(
            "lf.pipeline.llm_factory.call_openrouter_api",
            return_value=("Model not found: x", None),
        ):
            with pytest.raises(RuntimeError, match="LLM Engine falhou"):
                call_llm_via_opencode(system_prompt="sys", user_prompt="usr", cache=False, mock=False)


def test_gate_raises_on_opencode_fallback_error_in_stderr():
    """Fallback subprocess: erro de modelo em stderr com success=True → RuntimeError."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-test-key"}, clear=True):
        with patch("lf.pipeline.llm_factory.call_openrouter_api", side_effect=Exception("OpenRouter 500")):
            with patch("lf.runner.opencode.llm.OpenCodeRunner") as mock_runner_cls:
                mock_runner = MagicMock()
                mock_runner.run.return_value = OpenCodeResult(
                    exit_code=0,
                    stdout="[MOCK OPENCODE] Executed prompt: ...",
                    stderr="UnknownError: upstream model error",
                )
                mock_runner_cls.return_value = mock_runner

                with pytest.raises(RuntimeError, match="LLM Engine falhou"):
                    call_llm_via_opencode(system_prompt="sys", user_prompt="usr", cache=False, mock=False)


def test_gate_pass_on_normal_response():
    """Resposta LLM normal (sem marcador de erro) passa pelo gate sem exceção."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=True):
        with patch("lf.runner.opencode.llm.OpenCodeRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = OpenCodeResult(
                exit_code=0,
                stdout="def add(a, b):\n    return a + b",
                stderr="",
            )
            mock_runner_cls.return_value = mock_runner

            res = call_llm_via_opencode(system_prompt="sys", user_prompt="usr", cache=False, mock=False)
            assert "return a + b" in res


def test_project_root_forwarded_to_opencode_runner(tmp_path):
    """C3: project_root passado a call_llm_via_opencode chega ao OpenCodeRunner.run."""
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": ""}, clear=True):
        with patch("lf.runner.opencode.llm.OpenCodeRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = OpenCodeResult(exit_code=0, stdout="ok output", stderr="")
            mock_runner_cls.return_value = mock_runner

            res = call_llm_via_opencode(
                system_prompt="sys",
                user_prompt="usr",
                cache=False,
                mock=False,
                project_root=str(tmp_path),
            )
            assert res == "ok output"
            mock_runner.run.assert_called_once()
            assert mock_runner.run.call_args.kwargs["project_root"] == str(tmp_path)


def test_raise_if_llm_error_marker_direct():
    """Helper do gate: marcadores em texto puro ou em stdout/stderr do result."""
    _raise_if_llm_error_marker("all good here")  # não levanta

    with pytest.raises(RuntimeError, match="model_not_found"):
        _raise_if_llm_error_marker("error code model_not_found")

    with pytest.raises(RuntimeError, match="LLM Engine falhou"):
        _raise_if_llm_error_marker(
            "stdout ok",
            OpenCodeResult(exit_code=0, stdout="ok", stderr="Unexpected server error"),
        )
