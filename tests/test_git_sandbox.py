"""Testes de cobertura para src/lf/runner/git/sandbox.py (GitSandbox).

Usa git real em tmp_path — o alvo é a lógica do sandbox, não o git em si.
Contém teste documentando BUG conhecido de merge_worktree (target_branch ignorado).
"""

import subprocess
from pathlib import Path

import pytest

from lf.runner.git.sandbox import GitSandbox


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Executa git em repo com stdout/stderr capturados."""
    return subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=check)


def _branch_list(repo: Path, branch: str) -> str:
    return _git(repo, "branch", "--list", branch).stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Repo git real com commit base na branch main."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main", "-q")
    _git(repo, "config", "user.email", "tester@loopforge.dev")
    _git(repo, "config", "user.name", "LoopForge Tester")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-m", "base")
    return repo


def _commit_in_worktree(path: Path, msg: str) -> None:
    _git(path, "add", "-A")
    _git(path, "commit", "-m", msg)


class TestPaths:
    def test_worktree_dir_under_slim(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.worktree_dir == git_repo / ".slim" / "worktrees"

    def test_repo_path_resolved(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir()
        sandbox = GitSandbox(repo)
        assert sandbox.repo_path == repo.resolve()


class TestCreateWorktree:
    def test_creates_dir_and_branch(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        path = sandbox.create_worktree("task-1")
        assert path is not None
        assert path == git_repo / ".slim" / "worktrees" / "task-1"
        assert path.exists()
        assert _branch_list(git_repo, "lf-worktree-task-1") != ""
        assert "task-1" in _git(git_repo, "worktree", "list").stdout

    def test_returns_none_on_non_git_dir(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        sandbox = GitSandbox(plain)
        assert sandbox.create_worktree("task-x") is None

    def test_reuses_existing_branch(self, git_repo: Path) -> None:
        """Fallback: branch já existe (worktree removida manualmente) → git worktree add <path> <branch>."""
        sandbox = GitSandbox(git_repo)
        first = sandbox.create_worktree("fallback")
        assert first is not None
        _git(git_repo, "worktree", "remove", "--force", str(first))
        # branch lf-worktree-fallback mantida de propósito
        assert _branch_list(git_repo, "lf-worktree-fallback") != ""
        second = sandbox.create_worktree("fallback")
        assert second is not None
        assert second.exists()

    def test_recreates_existing_dir(self, git_repo: Path) -> None:
        """Criação dupla: target existe → cleanup + recriação."""
        sandbox = GitSandbox(git_repo)
        first = sandbox.create_worktree("dup")
        assert first is not None
        second = sandbox.create_worktree("dup")
        assert second is not None
        assert second == first
        assert second.exists()
        assert _branch_list(git_repo, "lf-worktree-dup") != ""


class TestMergeWorktree:
    def _setup_worktree_with_change(self, git_repo: Path, task_id: str) -> Path:
        sandbox = GitSandbox(git_repo)
        path = sandbox.create_worktree(task_id)
        assert path is not None
        with (path / "base.txt").open("a") as f:
            f.write("change\n")
        _commit_in_worktree(path, f"wt change {task_id}")
        return path

    def test_merges_into_current_branch(self, git_repo: Path) -> None:
        """Comportamento real: merge aplicado na branch corrente, não em target_branch.

        Documenta BUG em sandbox.py:46 — target_branch é ignorado, sem checkout do alvo.
        """
        _git(git_repo, "checkout", "-b", "develop")
        self._setup_worktree_with_change(git_repo, "cur")
        sandbox = GitSandbox(git_repo)
        assert sandbox.merge_worktree("cur", target_branch="main") is True
        dev_log = _git(git_repo, "log", "develop", "--oneline").stdout
        main_log = _git(git_repo, "log", "main", "--oneline").stdout
        assert "feat: merge worktree cur" in dev_log
        assert "feat: merge worktree cur" not in main_log  # BUG: deveria estar em main

    @pytest.mark.xfail(
        strict=False,
        reason="BUG sandbox.py:46 — merge_worktree ignora target_branch; merge cai na branch corrente",
    )
    def test_respects_target_branch(self, git_repo: Path) -> None:
        """Contrato esperado: merge deve ir para target_branch mesmo estando em outra branch."""
        _git(git_repo, "checkout", "-b", "develop")
        self._setup_worktree_with_change(git_repo, "tgt")
        sandbox = GitSandbox(git_repo)
        assert sandbox.merge_worktree("tgt", target_branch="main") is True
        main_log = _git(git_repo, "log", "main", "--oneline").stdout
        assert "feat: merge worktree tgt" in main_log  # falha hoje → xfail

    def test_conflict_returns_false(self, git_repo: Path) -> None:
        self._setup_worktree_with_change(git_repo, "conf")
        # divergência em main: mesma linha alterada
        with (git_repo / "base.txt").open("a") as f:
            f.write("main change\n")
        _git(git_repo, "add", "-A")
        _git(git_repo, "commit", "-m", "main change")
        sandbox = GitSandbox(git_repo)
        assert sandbox.merge_worktree("conf") is False
        assert _git(git_repo, "merge", "--abort", check=False).returncode in (0, 1)

    def test_missing_branch_returns_false(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.merge_worktree("ghost") is False


class TestCleanupWorktree:
    def test_removes_dir_and_branch(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        path = sandbox.create_worktree("rm-1")
        assert path is not None
        assert path.exists()
        assert sandbox.cleanup_worktree("rm-1") is True
        assert not path.exists()
        assert _branch_list(git_repo, "lf-worktree-rm-1") == ""
        assert "rm-1" not in _git(git_repo, "worktree", "list").stdout

    def test_force_removes_dirty_worktree(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        path = sandbox.create_worktree("dirty")
        assert path is not None
        (path / "untracked.txt").write_text("x\n")
        assert sandbox.cleanup_worktree("dirty") is True
        assert not path.exists()

    def test_nonexistent_returns_true(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.cleanup_worktree("nope") is True


class TestLegacyBranches:
    def test_create_sandbox_branch(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.create_sandbox_branch("feat/x") is True
        assert _branch_list(git_repo, "feat/x") != ""
        assert _git(git_repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feat/x"

    def test_create_sandbox_branch_fails_on_non_git(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        sandbox = GitSandbox(plain)
        assert sandbox.create_sandbox_branch("feat/x") is False

    def test_cleanup_branch(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.create_sandbox_branch("feat/del") is True
        assert sandbox.cleanup_branch("feat/del", target_branch="main") is True
        assert _branch_list(git_repo, "feat/del") == ""
        assert _git(git_repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"

    def test_cleanup_branch_missing_returns_false(self, git_repo: Path) -> None:
        sandbox = GitSandbox(git_repo)
        assert sandbox.cleanup_branch("ghost", target_branch="main") is False
