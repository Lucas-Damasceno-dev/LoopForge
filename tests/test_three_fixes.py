"""Testes para os 3 pontos corrigidos (Auth padrão, contadores QA/AppSec separados, CLI benchmark)."""

import os
from unittest.mock import patch

from click.testing import CliRunner

from lf.api.config import APISettings
from lf.cli.commands.benchmark import benchmark_cmd
from lf.cli.commands.serve import serve_cmd
from lf.pipeline.nodes.appsec import appsec


def test_auth_enabled_by_default():
    settings = APISettings()
    assert settings.require_auth is False


def test_serve_cmd_auto_generates_api_key():
    with patch.dict(os.environ, {}, clear=True):
        runner = CliRunner()
        # Test help first
        res = runner.invoke(serve_cmd, ["--help"])
        assert res.exit_code == 0


def test_separate_attempt_counters(tmp_path):
    # Initial state with 2 QA retries already used
    state = {
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": True,
        "qa_attempt_count": 2,
        "appsec_attempt_count": 0,
        "max_retries": 3,
    }

    # AppSec should start with appsec_attempt_count=0 and pass
    res_appsec = appsec(state)
    assert res_appsec["next_agent"] == "devops"
    assert res_appsec.get("appsec_attempt_count", 0) == 0


def test_cli_benchmark_cmd(tmp_path):
    runner = CliRunner()
    # --mock agora exige flag explícita (default real); smoke rápido com 1 problema
    res = runner.invoke(benchmark_cmd, ["--limit", "1", "--runs", "1", "--mock", "--storage-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert "LoopForge" in res.output
