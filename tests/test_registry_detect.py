from lf.config.registry import GoStackHandler, PythonStackHandler


def test_python_detect_ignores_loose_py_file_without_tests(tmp_path):
    (tmp_path / "main.py").write_text("print('ok')\n", encoding="utf-8")

    detected = PythonStackHandler().detect_test_command(str(tmp_path))

    assert detected is None


def test_python_detect_returns_pytest_with_test_file_in_tests_dir(tmp_path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    detected = PythonStackHandler().detect_test_command(str(tmp_path))

    assert detected == "pytest"


def test_python_detect_returns_pytest_with_conftest(tmp_path):
    (tmp_path / "conftest.py").write_text("", encoding="utf-8")

    detected = PythonStackHandler().detect_test_command(str(tmp_path))

    assert detected == "pytest"


def test_go_detect_requires_go_mod(tmp_path):
    (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")

    detected = GoStackHandler().detect_test_command(str(tmp_path))

    assert detected is None
