"""Testes do guard LF_API_TEST no GitCheckpointManager (checkpoint.py).

O guard impede que `git add .` + `git commit` automáticos varram arquivos para
commits durante testes da API (E2E artifacts). Com LF_API_TEST=1,
``create_checkpoint`` retorna "" e não toca no repositório.
"""

import subprocess

import pytest


@pytest.fixture
def git_repo(tmp_path):
    """Repo git limpo com um arquivo untracked."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "config", "user.email", "tester@loopforge.local"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=tmp_path, check=True)
    (tmp_path / "file.txt").write_text("untracked")
    return tmp_path


def test_create_checkpoint_guard_lf_api_test(git_repo, monkeypatch):
    """LF_API_TEST=1 → create_checkpoint devolve "" e não cria commits."""
    from lf.runner.git.checkpoint import GitCheckpointManager

    monkeypatch.setenv("LF_API_TEST", "1")
    mgr = GitCheckpointManager(git_repo)
    result = mgr.create_checkpoint("guard")
    assert result == ""

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "5"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    # Sem commits: `git log` falha (exit != 0) com stdout vazio.
    assert log.stdout.strip() == ""
    assert log.returncode != 0


def test_create_checkpoint_sem_guard_commit(git_repo, monkeypatch):
    """Sem LF_API_TEST, create_checkpoint commita de verdade (devolve hash)."""
    from lf.runner.git.checkpoint import GitCheckpointManager

    monkeypatch.delenv("LF_API_TEST", raising=False)
    mgr = GitCheckpointManager(git_repo)
    result = mgr.create_checkpoint("real")
    assert result

    log = subprocess.run(
        ["git", "log", "--oneline", "-n", "1"],
        cwd=git_repo,
        capture_output=True,
        text=True,
    )
    assert log.returncode == 0
    assert "checkpoint: real" in log.stdout
