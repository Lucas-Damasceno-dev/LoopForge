"""Testes de execução real do OpenCodeRunner e TestHarnessRunner."""
import shutil
from pathlib import Path
from lf.runner.opencode.runner import OpenCodeRunner
from lf.runner.harness.runner import TestHarnessRunner


def test_opencode_runner_initialization():
    runner = OpenCodeRunner(model="oc/deepseek-v4-flash-free", timeout_seconds=10)
    assert runner.model == "oc/deepseek-v4-flash-free"
    assert runner.timeout_seconds == 10


def test_opencode_runner_mock_or_execution(tmp_path):
    runner = OpenCodeRunner(model="oc/deepseek-v4-flash-free", timeout_seconds=5)
    # Executa run com prompt simples
    res = runner.run(prompt="echo 'Hello LoopForge'", work_dir=str(tmp_path))
    assert res is not None
    assert hasattr(res, "success")
    assert hasattr(res, "output")


def test_harness_runner_detection(tmp_path):
    # Cria pom.xml fake para testar detecção de Java Maven
    pom = tmp_path / "pom.xml"
    pom.write_text("<project></project>")

    harness = TestHarnessRunner()
    detected = harness.detect_framework(str(tmp_path))
    assert detected is not None
    assert detected.language == "java"
    assert detected.testing_harness == "junit"
