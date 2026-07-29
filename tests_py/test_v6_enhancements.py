"""Suíte de testes para as novas funcionalidades e refatorações da branch feature/antigravity-v6-features."""
import pytest
from pathlib import Path
from click.testing import CliRunner

from lf.runner.harness.runner import TestHarnessRunner, TestHarnessResult
from lf.runner.harness.parser import parse_test_output
from lf.telemetry.benchmark_dataset import CURATED_BENCHMARK_PROBLEMS
from lf.memory.manager import MemoryManager
from lf.cli.commands.export import export_cmd
from lf.cli.commands.diff import diff_cmd
from lf.cli.commands.studio import studio_cmd


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


def test_memory_manager(tmp_path):
    db_file = tmp_path / "memory.sqlite"
    mem = MemoryManager(db_path=str(db_file))
    
    mem.save_lesson(run_id="run-101", stack="python", idea="API REST FastAPI", lesson_text="Usar Pydantic v2 para esquemas rigorosos.")
    lessons = mem.search_relevant_lessons(query="FastAPI", stack="python")
    
    assert len(lessons) > 0
    assert "Pydantic v2" in lessons[0]["lesson_text"]


def test_cli_export_command(tmp_path):
    runner = CliRunner()
    sample = tmp_path / "app.py"
    sample.write_text("print('hello')", encoding="utf-8")

    res = runner.invoke(export_cmd, ["--dir", str(tmp_path), "--output", str(tmp_path / "pack.zip")])
    assert res.exit_code == 0
    assert (tmp_path / "pack.zip").exists()


def test_cli_diff_interactive(tmp_path):
    runner = CliRunner()
    res = runner.invoke(diff_cmd, ["--target-dir", str(tmp_path), "--interactive"])
    assert res.exit_code == 0


def test_cli_studio_command():
    runner = CliRunner()
    res = runner.invoke(studio_cmd, ["--duration", "1"])
    assert res.exit_code == 0
    assert "Terminal Studio" in res.output
