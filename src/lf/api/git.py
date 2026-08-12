"""Rotas Git (ADE — GitPanel).

Tier2 do BLUEPRINT: expõe o estado do repositório git da run.

- ``GET /api/v1/git/{run_id}``: branch, HEAD, status curto (estilo ``git
  status --short``, por path) e log de commits (máx. 20) do repositório da run.

Resolução do caminho: a API cria o workdir de cada run em
``/tmp/loopforge/run_{run_id}`` (``_run_pipeline`` em lf/api/app.py escreve
``shared_state={"project_dir": ..., "output_dir": ...}`` apontando para esse
diretório). Como fallback robusto, também aceita ``/tmp/loopforge/run-{id}``
(forma de project_id ``run-{id}`` usada pelo dispatcher) e varre subdiretórios
de ``/tmp/loopforge`` cujo nome contenha o run_id — cobre runs criadas antes
de a convenção ser fixada. A raiz é uma constante de módulo (``_RUNS_ROOT``),
sobrescrevível em testes.

Regra de ouro: diretório inexistente ou sem repositório git → 404 com
mensagem clara (nunca 500).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from pydantic import BaseModel, Field

git_router = APIRouter(prefix="/api/v1/git", tags=["Git"])

# Raiz dos workdirs de runs criados pela API (mesmo padrão de lf/api/app.py).
# Constante de módulo: testes monkeypatcham para tmp_path hermético.
_RUNS_ROOT = Path("/tmp/loopforge")

# Limite de commits devolvidos no log (BLUEPRINT: log limit 20).
_LOG_LIMIT = 20


class GitStatusEntry(BaseModel):
    """Arquivo alterado no working tree (estilo ``git status --short``)."""

    path: str = Field(..., description="Caminho relativo do arquivo")
    status: str = Field(..., description="Código curto de status (ex.: M, A, D, R, ??)")


class GitLogEntry(BaseModel):
    """Um commit do histórico (máx. ``_LOG_LIMIT``)."""

    hash: str = Field(..., description="Hash curto (7 chars) do commit")
    subject: str = Field(..., description="Mensagem (primeira linha) do commit")
    author: str = Field(..., description="Nome do autor do commit")
    when: str = Field(..., description="Data do commit em ISO 8601")


class GitInfo(BaseModel):
    """Estado do repositório git da run."""

    branch: str | None = Field(None, description="Branch atual (None em HEAD detached/sem commits)")
    head: str | None = Field(None, description="Hash curto (7 chars) do HEAD (None sem commits)")
    status: list[GitStatusEntry] = Field(default_factory=list, description="Alterações no working tree")
    log: list[GitLogEntry] = Field(default_factory=list, description="Histórico de commits")


def _run_dir_candidates(run_id: str) -> list[Path]:
    """Candidatos de diretório da run, em ordem de prioridade."""
    base = _RUNS_ROOT
    return [
        base / f"run_{run_id}",
        base / f"run-{run_id}",
    ]


def _resolve_run_dir(run_id: str) -> Path | None:
    """run_id → diretório do repositório da run (primeiro candidato que existe).

    Varre também subdiretórios de ``_RUNS_ROOT`` cujo nome contenha o run_id
    (fallback para runs antigas com convenção de pasta diferente).
    """
    for candidate in _run_dir_candidates(run_id):
        if candidate.is_dir():
            return candidate
    try:
        for child in _RUNS_ROOT.iterdir():
            if child.is_dir() and run_id in child.name and (child / ".git").exists():
                return child
    except OSError:
        pass
    return None


def _parse_status_short(repo: Repo) -> list[GitStatusEntry]:
    """Status curto (``git status --short``) por path.

    Cada linha tem 2 chars de código + espaço + path; renomeações aparecem
    como ``R  old -> new`` e são normalizadas para o path de destino.
    """
    try:
        raw = repo.git.status("--short")
    except Exception:
        return []
    entries: list[GitStatusEntry] = []
    for line in raw.splitlines():
        line = line.rstrip("\n")
        if len(line) < 3:
            continue
        code = line[:2].strip() or "??"
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            entries.append(GitStatusEntry(path=path, status=code))
    return entries


def _parse_log(repo: Repo, limit: int = _LOG_LIMIT) -> list[GitLogEntry]:
    """Log de commits (mais recentes primeiro, máx. ``limit``)."""
    try:
        commits = list(repo.iter_commits(max_count=limit))
    except Exception:
        return []
    entries: list[GitLogEntry] = []
    for commit in commits:
        when = commit.committed_datetime.isoformat() if commit.committed_datetime else ""
        entries.append(
            GitLogEntry(
                hash=commit.hexsha[:7],
                subject=commit.summary or "",
                author=commit.author.name or commit.author.email or "",
                when=when,
            )
        )
    return entries


def _build_git_info(repo: Repo) -> GitInfo:
    """Monta GitInfo a partir do Repo (HEAD detached/sem commits tolerados)."""
    branch: str | None = None
    try:
        branch = repo.active_branch.name
    except (TypeError, ValueError):
        branch = None  # HEAD detached (ou repo sem commits)
    head: str | None = None
    try:
        if repo.head.is_valid():
            head = repo.head.commit.hexsha[:7]
    except (ValueError, TypeError):
        head = None
    return GitInfo(
        branch=branch,
        head=head,
        status=_parse_status_short(repo),
        log=_parse_log(repo),
    )


@git_router.get("/{run_id}", response_model=GitInfo)
async def get_git_info(run_id: str) -> GitInfo:
    """Estado do repositório git da run (branch, HEAD, status curto, log)."""
    repo_dir = _resolve_run_dir(run_id)
    if repo_dir is None:
        raise HTTPException(
            status_code=404,
            detail=f"Diretório da run {run_id} não encontrado em {_RUNS_ROOT}",
        )
    try:
        repo = Repo(repo_dir)
    except (InvalidGitRepositoryError, NoSuchPathError):
        raise HTTPException(
            status_code=404,
            detail=f"Diretório da run {run_id} não é um repositório git",
        )
    return _build_git_info(repo)
