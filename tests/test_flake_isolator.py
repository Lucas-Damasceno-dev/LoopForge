import subprocess

from lf.runner.harness.flake_isolator import FlakeIsolator


def test_init_sets_absolute_project_dir(tmp_path):
    isolator = FlakeIsolator(str(tmp_path))
    assert isolator.project_dir == str(tmp_path.resolve())


def test_is_preexisting_flake_returns_false_when_test_cmd_empty(tmp_path):
    isolator = FlakeIsolator(str(tmp_path))
    assert isolator.is_preexisting_flake("test_x", "") is False


def test_is_preexisting_flake_returns_true_on_nondeterministic_results(tmp_path, monkeypatch):
    isolator = FlakeIsolator(str(tmp_path))

    calls = {"count": 0}

    def _fake_run(*args, **kwargs):
        calls["count"] += 1
        rc = 0 if calls["count"] == 1 else 1
        return subprocess.CompletedProcess(args=args, returncode=rc, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = isolator.is_preexisting_flake("test_mod::test_a", "pytest -k test_a")
    assert result is True
    assert calls["count"] == 2


def test_is_preexisting_flake_returns_false_on_consistent_results(tmp_path, monkeypatch):
    isolator = FlakeIsolator(str(tmp_path))

    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    assert isolator.is_preexisting_flake("test_mod::test_b", "pytest -k test_b") is False


def test_is_preexisting_flake_returns_false_when_subprocess_raises(tmp_path, monkeypatch):
    isolator = FlakeIsolator(str(tmp_path))

    def _fake_run(*args, **kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr("subprocess.run", _fake_run)

    assert isolator.is_preexisting_flake("test_mod::test_c", "pytest -k test_c") is False


def test_filter_flaky_failures_splits_legitimate_and_flaky(tmp_path, monkeypatch):
    isolator = FlakeIsolator(str(tmp_path))
    failed = [
        {"name": "test_mod::test_ok", "error": "fail"},
        {"name": "test_mod::test_flaky", "error": "fail"},
        {"error": "sem nome"},
    ]

    def _fake_is_flake(test_name, test_cmd):
        return test_name == "test_mod::test_flaky"

    monkeypatch.setattr(isolator, "is_preexisting_flake", _fake_is_flake)

    legitimate, flaky = isolator.filter_flaky_failures(failed, "pytest")

    assert flaky == [{"name": "test_mod::test_flaky", "error": "fail"}]
    assert legitimate == [
        {"name": "test_mod::test_ok", "error": "fail"},
        {"error": "sem nome"},
    ]


def test_filter_flaky_failures_handles_empty_input(tmp_path):
    isolator = FlakeIsolator(str(tmp_path))
    legitimate, flaky = isolator.filter_flaky_failures([], "pytest")
    assert legitimate == []
    assert flaky == []
