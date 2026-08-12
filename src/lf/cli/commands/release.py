import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import click
from rich.console import Console

console = Console()

DEFAULT_VERSION = "0.1.0"
GIT_LOG_DEFAULT_N = 30

_CONVENTIONAL_RE = re.compile(r"^(feat|fix|refactor|chore|docs|test|perf|build|ci|style|revert)(\([^)]*\))?!?:\s+(.+)$")

_GROUP_TITLES = {
    "feat": "🚀 Funcionalidades",
    "fix": "🐛 Correções",
    "refactor": "♻️ Refatorações",
    "chore": "🧹 Tarefas internas",
    "docs": "📚 Documentação",
    "test": "🧪 Testes",
    "perf": "⚡ Performance",
    "build": "📦 Build",
    "ci": "🔧 CI/CD",
    "style": "🎨 Estilo",
    "revert": "↩️ Reversões",
    "commits": "📦 Commits",
}


def _git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True)


def is_git_repo() -> bool:
    return _git(["rev-parse", "--is-inside-work-tree"]).returncode == 0


def last_tag() -> str | None:
    """Retorna a tag mais recente alcançável a partir de HEAD (None se não houver)."""
    res = _git(["describe", "--tags", "--abbrev=0"])
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return res.stdout.strip()


def commits_since_tag(tag: str) -> list[str]:
    res = _git(["log", f"{tag}..HEAD", "--oneline", "--no-decorate"])
    if res.returncode != 0:
        return []
    return [line for line in res.stdout.splitlines() if line.strip()]


def last_commits(n: int = GIT_LOG_DEFAULT_N) -> list[str]:
    res = _git(["log", "-n", str(n), "--oneline", "--no-decorate"])
    if res.returncode != 0:
        return []
    return [line for line in res.stdout.splitlines() if line.strip()]


def bump_patch(version: str) -> str:
    """Incrementa o patch de uma versão semântica ('v6.0.0' -> '6.0.1')."""
    m = re.match(r"^v?(\d+)\.(\d+)\.(\d+)", version)
    if not m:
        return DEFAULT_VERSION
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{major}.{minor}.{patch + 1}"


def resolve_version(version: str | None) -> str:
    """Versão explícita > patch bump da última tag > default documentado (0.1.0)."""
    if version:
        return version
    tag = last_tag()
    if tag:
        return bump_patch(tag)
    return DEFAULT_VERSION


def _commit_subject(line: str) -> str:
    """Remove o short-hash do git log --oneline (ex.: 'a1b2c3d feat: x' -> 'feat: x')."""
    return re.sub(r"^[0-9a-f]{7,40}\s+", "", line)


def group_commits(commits: list[str]) -> dict[str, list[str]]:
    """Agrupa commits por tipo conventional-commit; demais caem em 'commits'."""
    groups: dict[str, list[str]] = {}
    for line in commits:
        m = _CONVENTIONAL_RE.match(_commit_subject(line))
        if m:
            groups.setdefault(m.group(1), []).append(f"- {m.group(3)}")
        else:
            groups.setdefault("commits", []).append(f"- {line}")
    return groups


def build_release_notes(version: str, date_str: str, commits: list[str]) -> str:
    """Monta as notas de release a partir do intervalo de commits."""
    groups = group_commits(commits)
    lines = [f"## [{version}] - {date_str}", ""]

    if not commits:
        lines += ["_Nenhum commit novo desde a última tag._", ""]
    else:
        for key in (
            "feat",
            "fix",
            "refactor",
            "chore",
            "docs",
            "test",
            "perf",
            "build",
            "ci",
            "style",
            "revert",
            "commits",
        ):
            items = groups.get(key)
            if not items:
                continue
            lines += [f"### {_GROUP_TITLES[key]}", *items, ""]

    return "\n".join(lines).rstrip() + "\n"


@click.command(name="release")
@click.argument("version", default=None, required=False)
@click.option("--dry-run", is_flag=True, default=False, help="Apenas exibe as notas sem atualizar o CHANGELOG.md")
def release_cmd(version: str | None, dry_run: bool):
    """Gera notas de release a partir do histórico git e atualiza o CHANGELOG.md.

    Sem argumento de versão: patch bump da última tag git; sem tags, usa 0.1.0.
    """
    if not is_git_repo():
        console.print("[yellow]Aviso: diretório atual não é um repositório git — notas sem histórico.[/yellow]")

    resolved = resolve_version(version)
    now_date = datetime.now(UTC).strftime("%Y-%m-%d")

    tag = last_tag()
    commits = commits_since_tag(tag) if tag else []
    if not commits:
        commits = last_commits(GIT_LOG_DEFAULT_N)

    release_notes = build_release_notes(resolved, now_date, commits)

    if dry_run:
        console.print("[bold yellow]--- NOTAS DE RELEASE (DRY RUN) ---[/bold yellow]")
        console.print(release_notes)
        return

    changelog_path = Path("CHANGELOG.md")
    if changelog_path.exists():
        existing = changelog_path.read_text(encoding="utf-8")
        new_content = f"# Changelog\n\n{release_notes}\n" + existing.replace("# Changelog\n\n", "")
    else:
        new_content = f"# Changelog\n\n{release_notes}\n"

    changelog_path.write_text(new_content, encoding="utf-8")
    console.print(f"[bold green]✓ Versão {resolved} lançada e registrada no CHANGELOG.md com sucesso![/bold green]")
