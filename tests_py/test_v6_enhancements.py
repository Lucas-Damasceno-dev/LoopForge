"""Suíte de testes para as novas funcionalidades e refatorações da branch feature/v6-enhancements."""
import pytest
from pathlib import Path
from lf.runner.harness.runner import TestHarnessRunner, TestHarnessResult
from lf.runner.harness.parser import parse_test_output
from lf.telemetry.benchmark_dataset import CURATED_BENCHMARK_PROBLEMS


def test_harness_runner_java_maven_detection(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text("<project></project>", encoding="utf-8")
    
    runner = TestHarnessRunner(stack="java")
    cmd = runner._detect_command(tmp_path)
    assert cmd == "mvn test"


def test_harness_runner_java_gradle_detection(tmp_path):
    gradle_file = tmp_path / "build.gradle"
    gradle_file.write_text("// gradle", encoding="utf-8")
    gradlew = tmp_path / "gradlew"
    gradlew.write_text("#!/bin/sh", encoding="utf-8")
    
    runner = TestHarnessRunner(stack="java")
    cmd = runner._detect_command(tmp_path)
    assert cmd == "./gradlew test"


def test_maven_test_output_parser():
    mvn_output = """
    [INFO] Running com.example.TaskApiApplicationTest
    [INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 1.2s
    [INFO] BUILD SUCCESS
    """
    parsed = parse_test_output(mvn_output)
    assert parsed["total"] == 5
    assert parsed["passed"] == 5
    assert parsed["failed"] == 0


def test_expanded_elo_benchmark_dataset():
    assert len(CURATED_BENCHMARK_PROBLEMS) == 15
    problem_ids = [p.id for p in CURATED_BENCHMARK_PROBLEMS]
    assert "P-011" in problem_ids
    assert "P-015" in problem_ids
