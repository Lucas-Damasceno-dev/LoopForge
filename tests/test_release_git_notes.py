"""Testes das notas de release geradas a partir do histórico git ('lf release')."""

from __future__ import annotations

import subprocess

from click.testing import CliRunner

from lf.cli.commands.release import release_cmd


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def _init_repo(tmp_path, commits: list[str], tag: str | None = None) -> None:
    _git("init", "-q", cwd=tmp_path)
    _git("config", "user.email", "test@loopforge", cwd=tmp_path)
    _git("config", "user.name", "Test", cwd=tmp_path)
    for i, msg in enumerate(commits):
        (tmp_path / f"file_{i}.txt").write_text(msg, encoding="utf-8")
        _git("add", ".", cwd=tmp_path)
        _git("commit", "-q", "-m", msg, cwd=tmp_path)
    if tag:
        _git("tag", tag, cwd=tmp_path)


def test_release_patch_bump_e_agrupamento_conventional(tmp_path):
    commits = [
        "v1.2.0: base",
        "feat: adiciona busca semântica",
        "fix: corrige timeout do runner",
        "chore: limpa dependências",
        "checkpoint: loopforge/task-run-abc",
    ]
    _init_repo(tmp_path, commits, tag="v1.2.0")

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, ["--dry-run"])

    assert res.exit_code == 0
    # Patch bump da última tag (v1.2.0 -> 1.2.1).
    assert "## [1.2.1] -" in res.output
    assert "### 🚀 Funcionalidades" in res.output
    assert "- adiciona busca semântica" in res.output
    assert "### 🐛 Correções" in res.output
    assert "- corrige timeout do runner" in res.output
    assert "### 🧹 Tarefas internas" in res.output
    # Commit sem prefixo conventional cai na lista plana.
    assert "### 📦 Commits" in res.output
    assert "- checkpoint: loopforge/task-run-abc" in res.output


def test_release_sem_tag_usa_default_0_1_0_e_ultimos_commits(tmp_path):
    _init_repo(tmp_path, ["feat: primeira feature", "fix: ajuste inicial"])

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, ["--dry-run"])

    assert res.exit_code == 0
    assert "## [0.1.0] -" in res.output
    assert "- primeira feature" in res.output
    assert "- ajuste inicial" in res.output


def test_release_versao_explicita_prevalece(tmp_path):
    _init_repo(tmp_path, ["feat: algo"], tag="v1.0.0")

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, ["9.9.9", "--dry-run"])

    assert res.exit_code == 0
    assert "## [9.9.9] -" in res.output
    assert "## [1.0.1]" not in res.output


def test_release_escreve_changelog(tmp_path):
    _init_repo(tmp_path, ["feat: funcionalidade nova"], tag="v2.0.0")

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, [])

    assert res.exit_code == 0
    changelog = tmp_path / "CHANGELOG.md"
    assert changelog.exists()
    content = changelog.read_text(encoding="utf-8")
    assert "## [2.0.1] -" in content
    assert "- funcionalidade nova" in content
    assert "lançada e registrada no CHANGELOG.md" in res.output


def test_release_fora_de_repo_git_avisa_e_usa_default(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, ["--dry-run"])

    assert res.exit_code == 0
    assert "não é um repositório git" in res.output
    assert "## [0.1.0] -" in res.output
