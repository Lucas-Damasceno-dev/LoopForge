"""Testes do GitSandbox (roadmap 4.1) — worktrees isoladas com merge após aprovação.

Repos locais em tmp_path com git init (git config local — sem tocar no repo real).
"""

import subprocess
from pathlib import Path

from lf.runner.git.sandbox import GitSandbox


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=path, check=True)
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout


def test_is_git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    assert GitSandbox.is_git_repo(repo) is True
    subdir = repo / "sub"
    subdir.mkdir()
    assert GitSandbox.is_git_repo(subdir) is True

    plain = tmp_path / "plain"
    plain.mkdir()
    assert GitSandbox.is_git_repo(plain) is False
    assert GitSandbox.is_git_repo(tmp_path / "nao_existe") is False


def test_create_worktree_commit_merge_na_main(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    wt = sb.create_worktree("task-1")
    assert wt is not None
    assert wt.exists()
    assert ".slim" in wt.parts and "worktrees" in wt.parts

    (wt / "app.py").write_text("print('oi')\n", encoding="utf-8")
    assert sb.commit_worktree("task-1", "feat: código gerado por task-1") is True
    assert sb.merge_worktree("task-1") is True

    # Conteúdo mergeado na main
    assert (repo / "app.py").read_text(encoding="utf-8") == "print('oi')\n"
    # Merge commit --no-ff presente no log da main
    log = _git(repo, "log", "--format=%s", "main")
    assert "feat: merge worktree task-1" in log

    assert sb.cleanup_worktree("task-1") is True
    assert not wt.exists()


def test_merge_conflito_aborta_e_restaura(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    wt = sb.create_worktree("task-c")
    assert wt is not None
    # Worktree altera arquivo já rastreado (mesma linha da main)
    (wt / "README.md").write_text("# worktree edit\n", encoding="utf-8")
    assert sb.commit_worktree("task-c", "feat: wt edit") is True

    # Divergência na main: mesma linha de README.md alterada e commitada
    (repo / "README.md").write_text("# main edit\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "main change"], cwd=repo, check=True)

    assert sb.merge_worktree("task-c") is False

    # Sem estado MERGING (merge --abort executado) e branch original restaurada
    merge_head = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"], cwd=repo, capture_output=True
    ).returncode
    assert merge_head != 0
    branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    assert branch == "main"
    # Conteúdo da main preservado (conflito não vazou)
    assert (repo / "README.md").read_text(encoding="utf-8") == "# main edit\n"


def test_cleanup_remove_worktree_e_branch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    wt = sb.create_worktree("task-d")
    assert wt is not None
    assert sb.cleanup_worktree("task-d") is True
    assert not wt.exists()

    branches = _git(repo, "branch", "--list", "lf-worktree-task-d")
    assert "lf-worktree-task-d" not in branches


def test_create_worktree_idempotente(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    w1 = sb.create_worktree("task-e")
    assert w1 is not None
    # Segunda criação do MESMO task_id: limpa a anterior e recria
    w2 = sb.create_worktree("task-e")
    assert w2 is not None
    assert w1 == w2
    assert w1.exists()


def test_commit_ignora_artefatos(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    wt = sb.create_worktree("task-f")
    assert wt is not None
    (wt / "main.py").write_text("x = 1\n", encoding="utf-8")
    venv_bin = wt / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("junk", encoding="utf-8")
    pycache = wt / "__pycache__"
    pycache.mkdir()
    (pycache / "a.cpython-311.pyc").write_text("junk", encoding="utf-8")

    assert sb.commit_worktree("task-f", "feat: código") is True

    tracked = _git(wt, "ls-files")
    assert "main.py" in tracked
    assert ".venv/" not in tracked
    assert "__pycache__/" not in tracked


def test_commit_sem_mudancas_retorna_true(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    sb = GitSandbox(repo)

    wt = sb.create_worktree("task-g")
    assert wt is not None
    # Nada foi alterado na worktree — commit não tem o que gravar
    assert sb.commit_worktree("task-g", "feat: nada") is True
