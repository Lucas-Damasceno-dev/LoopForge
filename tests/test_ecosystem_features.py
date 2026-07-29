"""Testes dos recursos do Ecossistema: Multi-stack Harness, Benchmark Suite e Shell Completions."""

from click.testing import CliRunner

from lf.cli.commands.completion import completion_cmd
from lf.runner.harness.parser import parse_test_output
from lf.runner.harness.runner import TestHarnessRunner
from lf.telemetry.benchmark import BenchmarkSuite, RunBenchmark


def test_multi_stack_parser():
    # Pytest / Vitest / Jest
    res_py = parse_test_output("10 passed, 2 failed in 1.23s")
    assert res_py["passed"] == 10
    assert res_py["failed"] == 2

    # Go test
    res_go = parse_test_output("--- PASS: TestA\n--- PASS: TestB\n--- FAIL: TestC")
    assert res_go["passed"] == 2
    assert res_go["failed"] == 1

    # Cargo test
    res_cargo = parse_test_output("test result: ok. 5 passed; 0 failed")
    assert res_cargo["passed"] == 5
    assert res_cargo["failed"] == 0


def test_multi_stack_runner_detection(tmp_path):
    runner_py = TestHarnessRunner(stack="python")
    assert runner_py._detect_command(tmp_path) == "pytest"

    runner_go = TestHarnessRunner(stack="go")
    assert runner_go._detect_command(tmp_path) == "go test ./..."

    runner_rust = TestHarnessRunner(stack="rust")
    assert runner_rust._detect_command(tmp_path) == "cargo test"

    runner_ts = TestHarnessRunner(stack="typescript")
    assert runner_ts._detect_command(tmp_path) == "npm test"


def test_benchmark_suite(tmp_path):
    suite = BenchmarkSuite(storage_dir=str(tmp_path))
    bench = RunBenchmark(
        run_id="run-101",
        stack="python",
        idea="Build API",
        total_duration_seconds=5.2,
        estimated_cost_usd=0.002,
        success=True,
    )
    saved_path = suite.record_run(bench)
    assert "run_run-101.json" in saved_path


    summary = suite.get_summary()
    assert summary["total_runs"] == 1
    assert "python" in summary["by_stack"]
    assert summary["by_stack"]["python"]["success_rate"] == 100.0


def test_cli_completion_cmd():
    runner = CliRunner()
    res = runner.invoke(completion_cmd, ["--shell", "bash"])
    assert res.exit_code == 0
    assert "bash_source" in res.output

    res_zsh = runner.invoke(completion_cmd, ["--shell", "zsh"])
    assert "zsh_source" in res_zsh.output
