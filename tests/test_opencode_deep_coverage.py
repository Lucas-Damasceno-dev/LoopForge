"""Testes profundos para elevar a cobertura de opencode/runner.py e opencode/llm.py para >= 85%."""

import json
import os
import subprocess
import time
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.pipeline.llm_factory import SQLiteLLMCache
from lf.runner.opencode.llm import _extract_json_from_text, _mock_response, call_llm_via_opencode
from lf.runner.opencode.models import OpenCodeResult
from lf.runner.opencode.runner import OpenCodeRunner, detect_changed_files


class SampleSchemaModel(BaseModel):
    id: str = Field(...)
    title: str = Field(...)
    count: int = Field(0)
    score: float = Field(0.0)
    is_active: bool = Field(True)
    items: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


# ─── 1. Deep Tests for opencode/runner.py ────────────────────────────
def test_opencode_runner_circuit_breaker_open():
    cb = MagicMock(spec=CircuitBreaker)
    cb.can_proceed.return_value = False

    runner = OpenCodeRunner(timeout_seconds=10)
    res = runner.run("test prompt", circuit_breaker=cb)
    assert res.exit_code == 1
    assert "Circuit breaker is open" in res.stderr


def test_opencode_runner_real_subprocess_success(tmp_path):
    runner = OpenCodeRunner(timeout_seconds=10)
    with patch("shutil.which", return_value="/usr/bin/opencode"):
        with patch.dict(os.environ, {"OPENCODE_MOCK": "0"}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="opencode output", stderr=""
                )
                res = runner.run("create app", project_root=tmp_path)
                assert res.success is True
                assert res.stdout == "opencode output"


def test_opencode_runner_timeout_expired(tmp_path):
    runner = OpenCodeRunner(timeout_seconds=5)
    with patch("shutil.which", return_value="/usr/bin/opencode"):
        with patch.dict(os.environ, {"OPENCODE_MOCK": "0"}):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired(cmd="opencode", timeout=5, output="partial")
                res = runner.run("slow task", project_root=tmp_path)
                assert res.exit_code == 124
                assert "timed out" in res.stderr


def test_opencode_runner_general_exception(tmp_path):
    runner = OpenCodeRunner(timeout_seconds=5)
    with patch("shutil.which", return_value="/usr/bin/opencode"):
        with patch.dict(os.environ, {"OPENCODE_MOCK": "0"}):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("OS Subprocess Error")
                res = runner.run("failing task", project_root=tmp_path)
                assert res.exit_code == 1
                assert "OS Subprocess Error" in res.stderr


def test_detect_changed_files_git_status(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    sample = tmp_path / "main.py"
    sample.write_text("print('hello')", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=" M main.py\n?? new_file.py\n"
        )
        changed = detect_changed_files(tmp_path, time.time() - 10)
        assert len(changed) > 0


def test_detect_changed_files_mtime_fallback(tmp_path):
    sample = tmp_path / "feature.py"
    sample.write_text("x = 1", encoding="utf-8")
    start_time = time.time() - 1.0

    changed = detect_changed_files(tmp_path, start_time)
    assert str(sample) in changed


# ─── 2. Deep Tests for opencode/llm.py ───────────────────────────────
def test_call_llm_cache_hit_and_miss(tmp_path):
    db_file = tmp_path / "test_cache.sqlite"
    cache = SQLiteLLMCache(db_path=db_file)

    prompt_key = "sys_cache\n\nuser_cache"
    cache.set(prompt_key, json.dumps({"id": "MOCK-001", "title": "Cached Title"}))

    with patch("lf.runner.opencode.llm.SQLiteLLMCache", return_value=cache):
        # Cache hit com schema
        res = call_llm_via_opencode(
            system_prompt="sys_cache",
            user_prompt="user_cache",
            schema_model=SampleSchemaModel,
            cache=True,
            mock=False,
        )
        assert res["title"] == "Cached Title"

        # Cache hit sem schema
        cache.set("text_sys\n\ntext_user", "Plain text cached")
        res_text = call_llm_via_opencode(
            system_prompt="text_sys",
            user_prompt="text_user",
            cache=True,
            mock=False,
        )
        assert res_text == "Plain text cached"


def test_call_llm_openrouter_success(tmp_path):
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-key"}):
        with patch("lf.pipeline.llm_factory.call_openrouter_api") as mock_api:
            mock_api.return_value = json.dumps({
                "id": "OR-001",
                "title": "OpenRouter Result",
                "count": 5,
                "score": 4.5,
                "is_active": True,
                "items": ["a"],
                "metadata": {"key": "val"}
            })

            res = call_llm_via_opencode(
                system_prompt="sys",
                user_prompt="usr",
                schema_model=SampleSchemaModel,
                cache=False,
                mock=False,
            )
            assert res["title"] == "OpenRouter Result"


def test_call_llm_openrouter_failure_fallback_opencode(tmp_path):
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-key"}):
        with patch("lf.pipeline.llm_factory.call_openrouter_api", side_effect=Exception("OpenRouter 500")):
            with patch.object(OpenCodeRunner, "run") as mock_runner_run:
                mock_runner_run.return_value = OpenCodeResult(
                    exit_code=0,
                    stdout=json.dumps({
                        "id": "FB-001",
                        "title": "Fallback Result",
                        "count": 1,
                        "score": 1.0,
                        "is_active": True,
                        "items": [],
                        "metadata": {}
                    }),
                    stderr="",
                )

                res = call_llm_via_opencode(
                    system_prompt="sys",
                    user_prompt="usr",
                    schema_model=SampleSchemaModel,
                    cache=False,
                    mock=False,
                )
                assert res["title"] == "Fallback Result"


def test_call_llm_no_openrouter_key_opencode_runner(tmp_path):
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=True):
        with patch.object(OpenCodeRunner, "run") as mock_runner_run:
            mock_runner_run.return_value = OpenCodeResult(
                exit_code=0,
                stdout="Plain text output from opencode",
                stderr="",
            )

            res = call_llm_via_opencode(
                system_prompt="sys",
                user_prompt="usr",
                cache=False,
                mock=False,
            )
            assert res == "Plain text output from opencode"


def test_call_llm_schema_invalid_json_raises_runtime_error():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-test-key"}):
        with patch("lf.pipeline.llm_factory.call_openrouter_api", return_value="INVALID NON-JSON TEXT"):
            with pytest.raises(RuntimeError) as exc_info:
                call_llm_via_opencode(
                    system_prompt="sys",
                    user_prompt="usr",
                    schema_model=SampleSchemaModel,
                    cache=False,
                    mock=False,
                )
            assert "LLM não retornou JSON válido" in str(exc_info.value)


def test_call_llm_opencode_runner_failure_raises():
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}, clear=True):
        with patch.object(OpenCodeRunner, "run") as mock_runner_run:
            mock_runner_run.return_value = OpenCodeResult(
                exit_code=1,
                stdout="",
                stderr="Fatal OpenCode Execution Failure",
            )
            with pytest.raises(RuntimeError) as exc_info:
                call_llm_via_opencode(
                    system_prompt="sys",
                    user_prompt="usr",
                    cache=False,
                    mock=False,
                )
            assert "OpenCode LLM call failed" in str(exc_info.value)


def test_mock_response_generator():
    mock_dict = _mock_response(SampleSchemaModel)
    assert mock_dict["id"] == "MOCK-001"
    assert isinstance(mock_dict["title"], str)
    assert isinstance(mock_dict["items"], list)
    assert isinstance(mock_dict["metadata"], dict)
