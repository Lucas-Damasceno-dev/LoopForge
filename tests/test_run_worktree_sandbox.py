"""Testes de ciclo de vida de Git Worktree Sandbox para Runs."""

import os
import subprocess
from pathlib import Path
import pytest

from lf.runner.git.sandbox import GitSandbox


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True, capture_output=True)
    readme = path / "README.md"
    readme.write_text("# Repo Test\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(path), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(path), check=True, capture_output=True)


def test_git_sandbox_create_and_cleanup(tmp_path: Path):
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    _init_git_repo(repo_dir)

    sandbox = GitSandbox(repo_dir)
    assert GitSandbox.is_git_repo(repo_dir) is True

    task_id = "run-12345678"
    wt_path = sandbox.create_worktree(task_id)
    assert wt_path is not None
    assert wt_path.exists()
    assert wt_path == repo_dir / ".slim" / "worktrees" / task_id

    # Cria arquivo na worktree
    gen_file = wt_path / "generated.py"
    gen_file.write_text("print('hello sandbox')\n")

    # Commita na worktree
    committed = sandbox.commit_worktree(task_id, "feat: generated code")
    assert committed is True

    # Merge da worktree
    merged = sandbox.merge_worktree(task_id, target_branch="master")
    if not merged:
        merged = sandbox.merge_worktree(task_id, target_branch="main")
    assert merged is True
    assert (repo_dir / "generated.py").exists()

    # Cleanup
    cleaned = sandbox.cleanup_worktree(task_id)
    assert cleaned is True
    assert not wt_path.exists()


def test_git_sandbox_non_git_repo(tmp_path: Path):
    non_git = tmp_path / "plain_dir"
    non_git.mkdir()

    assert GitSandbox.is_git_repo(non_git) is False
    sandbox = GitSandbox(non_git)
    wt = sandbox.create_worktree("run-non-git")
    assert wt is None
