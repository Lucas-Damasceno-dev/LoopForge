import json
from pathlib import Path

from lf.orchestrator.fail_to_eval import FailToEval


def test_init_creates_benchmarks_dir_and_sets_absolute_paths(tmp_path):
    rel_repo = tmp_path / "repo"
    rel_repo.mkdir()

    manager = FailToEval(str(rel_repo))

    assert manager.repo_root == str(rel_repo.resolve())
    assert manager.benchmarks_dir == str(rel_repo / ".loopforge" / "benchmarks")
    assert Path(manager.benchmarks_dir).is_dir()


def test_create_benchmark_case_writes_json_with_expected_fields(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = FailToEval(str(repo))

    output_path = manager.create_benchmark_case(
        task_id="task123",
        prompt="Implementar endpoint",
        initial_files={"a.py": "print('a')"},
        expected_patch_files={"a.py": "print('b')"},
    )

    output = Path(output_path)
    assert output.is_file()
    assert output.parent == repo / ".loopforge" / "benchmarks"
    assert output.name.startswith("bench_task123_")

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["benchmark_id"].startswith("bench_task123_")
    assert data["task_id"] == "task123"
    assert data["prompt"] == "Implementar endpoint"
    assert data["failure_reason"] == "QA Failure / Human Interrupt"
    assert data["initial_files"] == {"a.py": "print('a')"}
    assert data["expected_patch_files"] == {"a.py": "print('b')"}
    assert isinstance(data["created_at"], str)


def test_create_benchmark_case_uses_custom_failure_reason(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = FailToEval(str(repo))

    output_path = manager.create_benchmark_case(
        task_id="task456",
        prompt="Corrigir bug",
        initial_files={},
        expected_patch_files={},
        failure_reason="Timeout no QA",
    )

    data = json.loads(Path(output_path).read_text(encoding="utf-8"))
    assert data["failure_reason"] == "Timeout no QA"


def test_create_benchmark_case_raises_if_write_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    manager = FailToEval(str(repo))

    def _raise_ioerror(*args, **kwargs):
        raise OSError("sem permissao")

    monkeypatch.setattr("builtins.open", _raise_ioerror)

    try:
        manager.create_benchmark_case(
            task_id="task789",
            prompt="Teste",
            initial_files={},
            expected_patch_files={},
        )
    except OSError as exc:
        assert "sem permissao" in str(exc)
    else:
        raise AssertionError("Era esperado OSError durante escrita do benchmark")
