from pathlib import Path

from lf.runner.harness.bootstrap import bootstrap_project_environment
from lf.runner.harness.formatter import format_test_summary
from lf.runner.harness.parser import parse_test_output


def test_harness_bootstrap_and_parser(tmp_path: Path):
    bootstrap_project_environment(tmp_path)
    sample_file = tmp_path / "tests_py" / "test_sample.py"
    assert sample_file.exists()

    parsed = parse_test_output("5 passed, 1 failed in 2.3s")
    assert parsed["passed"] == 5
    assert parsed["failed"] == 1
    assert parsed["total"] == 6

    formatted = format_test_summary(6, 5, 1)
    assert "FAILED" in formatted
