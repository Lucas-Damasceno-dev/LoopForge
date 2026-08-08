from pathlib import Path


def bootstrap_project_environment(project_root: str | Path = ".") -> bool:
    """Bootstraps testing harness structure if missing."""
    root = Path(project_root)
    tests_dir = root / "tests_py"
    tests_dir.mkdir(parents=True, exist_ok=True)
    sample_test = tests_dir / "test_sample.py"
    if not sample_test.exists():
        sample_test.write_text("def test_sanity():\n    assert True\n", encoding="utf-8")
    return True
