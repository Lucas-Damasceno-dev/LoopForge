"""Suíte de testes para validar Benchmark ELO, GitHub Action, Otimizações LLM, Dashboard WS, CLI e Auditoria Paralela."""
import os
import pytest
from pathlib import Path
from click.testing import CliRunner

from lf.cli.commands.benchmark import benchmark_cmd
from lf.cli.main import main as cli_main
from lf.pipeline.llm_factory import SQLiteLLMCache, _semantic_normalize_prompt, compress_prompt
from lf.pipeline.nodes.parallel_audit import parallel_audit
from lf.telemetry.benchmark import BenchmarkSuite, RunBenchmark
from lf.telemetry.benchmark_dataset import CURATED_BENCHMARK_PROBLEMS


def test_curated_benchmark_dataset():
    assert len(CURATED_BENCHMARK_PROBLEMS) == 10
    assert CURATED_BENCHMARK_PROBLEMS[0].stack == "python"
    assert CURATED_BENCHMARK_PROBLEMS[4].stack == "rust"


def test_elo_calculation_and_storage(tmp_path):
    suite = BenchmarkSuite(storage_dir=str(tmp_path))
    initial_elo = suite.load_elo_rating()
    assert initial_elo == 1200.0

    delta_pass = suite.calculate_elo_delta(passed=10, total=10)
    assert delta_pass > 0  # +16.0 ELO gain

    prev, new_elo = suite.update_elo_rating(delta_pass)
    assert new_elo > prev

    summary = suite.get_summary()
    assert summary["current_elo"] == new_elo


def test_github_action_manifest_exists():
    action_path = Path("action.yml")
    assert action_path.exists()
    content = action_path.read_text(encoding="utf-8")
    assert "LoopForge AI Pipeline Governance" in content
    assert "openrouter_api_key" in content


def test_prompt_compression_and_semantic_cache(tmp_path):
    raw_prompt = "Line 1\n\n\nLine 2    with   extra   spaces\n\nLine 3"
    compressed = compress_prompt(raw_prompt)
    assert "\n\n\n" not in compressed

    norm1 = _semantic_normalize_prompt("Prompt with 2026-07-29T02:00:00Z timestamp")
    norm2 = _semantic_normalize_prompt("prompt   with    timestamp")
    assert norm1 == norm2

    cache = SQLiteLLMCache(db_path=tmp_path / "cache.sqlite")
    cache.set("Test Prompt 2026-07-29", "Cached Output")
    assert cache.get("test prompt") == "Cached Output"


def test_cli_essential_commands():
    runner = CliRunner()
    res = runner.invoke(cli_main, ["--help"])
    assert res.exit_code == 0
    assert "benchmark" in res.output
    assert "run" in res.output
    assert "serve" in res.output
    assert "resume" in res.output
    assert "diff" in res.output
    assert "explore" in res.output


def test_parallel_audit_execution(tmp_path):
    state = {
        "code": "def hello(): pass",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "mock_llm": True,
    }
    res = parallel_audit(state)
    assert "security_report" in res
    assert "devops_report" in res
    assert res["next_agent"] in ("FINISH", "developer")


def test_benchmark_cli_command(tmp_path):
    runner = CliRunner()
    res = runner.invoke(benchmark_cmd, ["--limit", "2", "--mock", "--storage-dir", str(tmp_path)])
    assert res.exit_code == 0
    assert "LoopForge ELO Rating" in res.output
