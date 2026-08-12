"""Testes da API de git (Tier2 — GitPanel da ADE).

Cobre:
- GET /api/v1/git/{run_id}: branch, HEAD, status curto (por path) e log de
  commits de um repositório git temporário (gitpython) no workdir da run.
- Run sem diretório → 404 com mensagem clara.
- Diretório da run sem repositório git → 404 com mensagem clara.

Padrão de test_api_evals: LF_API_TEST=1 + init_db em tmp_path hermético.
A raiz dos workdirs (_RUNS_ROOT) é monkeypatchada para tmp_path.
"""

from pathlib import Path

import git as gitlib
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


def _make_git_repo(repo_dir, *, commits: int = 2) -> None:
    """Cria repo git com `commits` commits, 1 arquivo modificado e 1 untracked."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    repo = gitlib.Repo.init(repo_dir)
    with repo.config_writer() as cw:
        cw.set_value("user", "name", "Test Bot")
        cw.set_value("user", "email", "bot@test.dev")

    if commits > 0:
        (repo_dir / "main.py").write_text("print('v0')\n", encoding="utf-8")
        repo.index.add(["main.py"])
        repo.index.commit("feat: init")

    if commits > 1:
        (repo_dir / "app.py").write_text("print('app')\n", encoding="utf-8")
        repo.index.add(["app.py"])
        repo.index.commit("feat: app")

    # working tree sujo: modificado + untracked
    if commits > 0:
        (repo_dir / "main.py").write_text("print('v1 changed')\n", encoding="utf-8")
    (repo_dir / "draft.txt").write_text("rascunho\n", encoding="utf-8")


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    """Banco SQLite limpo + _RUNS_ROOT apontando para tmp_path."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    import lf.api.git as git_module

    monkeypatch.setattr(git_module, "_RUNS_ROOT", tmp_path)
    await init_db()
    yield
    await close_db()
    monkeypatch.delenv("LF_API_TEST", raising=False)


def _client():
    return AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")


@pytest.mark.asyncio
async def test_get_git_info_returns_branch_head_status_and_log():
    """Repo git da run → 200 com branch, HEAD, status curto e log (máx 20)."""
    _make_git_repo(tmp_dir := Path("run_run-1"))
    repo = gitlib.Repo(tmp_dir)

    async with _client() as client:
        resp = await client.get("/api/v1/git/run-1")
    assert resp.status_code == 200
    body = resp.json()

    assert body["branch"] == repo.active_branch.name
    assert body["head"] == repo.head.commit.hexsha[:7]
    # status curto estilo git status --short (ordenado por path)
    assert {e["path"]: e["status"] for e in body["status"]} == {
        "draft.txt": "??",
        "main.py": "M",
    }
    assert len(body["log"]) == 2
    assert body["log"][0]["subject"] == "feat: app"
    assert body["log"][0]["hash"] == repo.head.commit.hexsha[:7]
    assert body["log"][0]["author"] == "Test Bot"
    assert body["log"][0]["when"]


@pytest.mark.asyncio
async def test_get_git_info_empty_repo_returns_empty_lists():
    """Repo sem commits → 200 com branch setada, head/status/log vazios."""
    _make_git_repo(tmp_dir := Path("run_fresh"), commits=0)
    repo = gitlib.Repo(tmp_dir)

    async with _client() as client:
        resp = await client.get("/api/v1/git/fresh")
    assert resp.status_code == 200
    body = resp.json()
    assert body["branch"] == repo.active_branch.name
    assert body["head"] is None
    # sem commits, draft.txt aparece apenas como untracked (??)
    assert body["status"] == [{"path": "draft.txt", "status": "??"}]
    assert body["log"] == []


@pytest.mark.asyncio
async def test_get_git_info_unknown_run_returns_404():
    """Run sem diretório → 404 com mensagem clara."""
    async with _client() as client:
        resp = await client.get("/api/v1/git/nope")
    assert resp.status_code == 404
    assert "não encontrado" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_git_info_dir_without_git_returns_404():
    """Diretório existe mas não é repo git → 404 com mensagem clara."""
    (Path("run_plain")).mkdir(parents=True)

    async with _client() as client:
        resp = await client.get("/api/v1/git/plain")
    assert resp.status_code == 404
    assert "não é um repositório git" in resp.json()["detail"]
