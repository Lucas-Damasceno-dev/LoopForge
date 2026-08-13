"""Testes da integração sandbox (roadmap 4.1) — TaskDispatcher + GitSandbox.

Fluxo: dispatch mock em repo git tmp → output_dir vira a worktree → após
aprovação, commit+merge na main; falha → worktree limpa SEM merge.

Nota: o nó developer (mock) escreve em [output_dir, project_dir]; com sandbox
ativa o project_dir é o cwd (repo) — para o merge não colidir com arquivos
untracked, o teste restringe a escrita à worktree (semântica pretendida da
sandbox). Padrão de fixture: tests/test_hitl_ux_enhancements.py.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest_asyncio

from lf.api.database import close_db, init_db
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=path, check=True)
    (path / "README.md").write_text("# repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=path, check=True)


def _main_log(repo: Path) -> str:
    return subprocess.run(["git", "log", "--format=%s", "main"], cwd=repo, capture_output=True, text=True).stdout


@pytest_asyncio.fixture(autouse=True)
async def repo(tmp_path, monkeypatch):
    """Repo git tmp + ade.yaml com sandbox_enabled + DBs de teste isolados."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("LF_WORKDIR_BASE", str(tmp_path / "workbase"))
    (repo / ".loopforge").mkdir(exist_ok=True)
    (repo / ".loopforge" / "ade.yaml").write_text("runner:\n  sandbox_enabled: true\n", encoding="utf-8")
    await init_db()
    yield repo
    await close_db()


def test_setup_sandbox_cria_worktree_e_snapshot(repo):
    dispatcher = TaskDispatcher(mock_llm=True)
    snap = dispatcher._setup_sandbox({"project_dir": ".", "idea": "x"}, TaskSchema(id="task-sb-1", title="t"))
    assert snap is not None
    assert snap["enabled"] is True
    assert snap["branch"] == f"lf-worktree-{snap['task_id']}"
    wt = Path(snap["worktree_path"])
    assert wt.exists()
    assert ".slim" in wt.parts and "worktrees" in wt.parts
    assert str(wt.resolve()).startswith(str(repo.resolve()))


def test_setup_sandbox_ignora_repo_loopforge(repo):
    (repo / ".loopforge.json").write_text("{}", encoding="utf-8")
    dispatcher = TaskDispatcher(mock_llm=True)
    snap = dispatcher._setup_sandbox({"project_dir": ".", "idea": "x"}, TaskSchema(id="task-sb-2", title="t"))
    assert snap is None


def test_setup_sandbox_desabilitado_sem_ade(repo, monkeypatch):
    (repo / ".loopforge" / "ade.yaml").write_text("runner:\n  sandbox_enabled: false\n", encoding="utf-8")
    dispatcher = TaskDispatcher(mock_llm=True)
    snap = dispatcher._setup_sandbox({"project_dir": ".", "idea": "x"}, TaskSchema(id="task-sb-3", title="t"))
    assert snap is None


def test_dispatch_mock_sandbox_output_dir_worktree_e_merge(repo):
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)
    task = TaskSchema(id="task-sand-1", title="Sandbox test", agent_id="cpo", stack="python")

    res = dispatcher.dispatch(task=task, project_id="proj-sand-1")

    assert not res.get("error")
    assert res.get("sandbox", {}).get("enabled") is True
    wt = Path(res["sandbox"]["worktree_path"])
    # output_dir (e project_dir) redirecionados para a worktree isolada
    assert res["output_dir"] == str(wt)
    assert res["project_dir"] == str(wt)
    # worktree removida após finalização
    assert not wt.exists()
    # merge commit na main (--no-ff) confirma a integração aprovada
    assert "feat: merge worktree" in _main_log(repo)


def test_finalize_sandbox_aprovado_mergeia_na_main(repo):
    dispatcher = TaskDispatcher(mock_llm=True)
    snap = dispatcher._setup_sandbox({"project_dir": ".", "idea": "x"}, TaskSchema(id="task-ok-1", title="t"))
    assert snap is not None
    wt = Path(snap["worktree_path"])
    (wt / "main.py").write_text("x = 1\n", encoding="utf-8")

    result = {
        "test_report": {"summary": {"tests_failed": 0}},
        "security_report": {"vulnerabilities_found": 0},
        "stack": "python",
        "error": None,
    }
    dispatcher._finalize_sandbox(snap, result, approved=True)

    assert not wt.exists()
    assert (repo / "main.py").read_text(encoding="utf-8") == "x = 1\n"
    assert "feat: merge worktree" in _main_log(repo)


def test_finalize_sandbox_falha_testes_sem_merge(repo):
    dispatcher = TaskDispatcher(mock_llm=True)
    snap = dispatcher._setup_sandbox({"project_dir": ".", "idea": "x"}, TaskSchema(id="task-fail-1", title="t"))
    assert snap is not None
    wt = Path(snap["worktree_path"])
    (wt / "main.py").write_text("x = 1\n", encoding="utf-8")

    result = {
        "test_report": {"summary": {"tests_failed": 2}},
        "security_report": {"vulnerabilities_found": 0},
        "stack": "python",
        "error": None,
    }
    dispatcher._finalize_sandbox(snap, result, approved=True)

    # Worktree limpa SEM merge — código descartado
    assert not wt.exists()
    assert "feat: merge worktree" not in _main_log(repo)
    assert not (repo / "main.py").exists()


def test_dispatch_erro_limpa_worktree_sem_merge(repo):
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)
    task = TaskSchema(id="task-err-1", title="boom", agent_id="cpo")

    class _FailingGraph:
        async def astream(self, *args, **kwargs):
            raise RuntimeError("boom")
            yield  # pragma: no cover

        async def aget_state(self, config):
            raise RuntimeError("boom")

    with patch.object(dispatcher, "_get_graph", return_value=_FailingGraph()):
        res = dispatcher.dispatch(task=task, project_id="proj-err-1")

    assert res.get("error")
    # Exception path: sandbox finalizada SEM merge e worktree removida
    assert "feat: merge worktree" not in _main_log(repo)
    worktrees_dir = repo / ".slim" / "worktrees"
    if worktrees_dir.exists():
        assert not any(worktrees_dir.iterdir())
