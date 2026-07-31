"""Testes de execução real do OpenCodeRunner e TestHarnessRunner."""
from pathlib import Path
from lf.runner.opencode.runner import OpenCodeRunner
from lf.runner.harness.runner import TestHarnessRunner
from lf.config.registry import TechStackRegistry


def test_opencode_runner_initialization():
    runner = OpenCodeRunner(timeout_seconds=10)
    assert runner.timeout == 10


def test_opencode_runner_mock_or_execution(tmp_path):
    runner = OpenCodeRunner(timeout_seconds=5)
    res = runner.run(prompt="echo 'Hello LoopForge'", project_root=str(tmp_path), model="oc/deepseek-v4-flash-free")
    assert res is not None
    assert hasattr(res, "exit_code")
    assert hasattr(res, "stdout")


def test_harness_runner_detection(tmp_path):
    # Cria pom.xml fake para testar detecção de Java Maven no Registry
    pom = tmp_path / "pom.xml"
    pom.write_text("<project></project>")

    detected = TechStackRegistry.detect_command(str(tmp_path))
    assert detected == "mvn test"

    harness = TestHarnessRunner()
    res = harness.run_tests(project_root=str(tmp_path))
    assert res is not None
    assert hasattr(res, "exit_code")
