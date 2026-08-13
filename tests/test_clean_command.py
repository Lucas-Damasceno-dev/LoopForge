"""Testes para o comando CLI 'lf clean'."""

from pathlib import Path
from click.testing import CliRunner

from lf.cli.commands.clean import clean_cmd


def test_clean_dry_run_does_not_delete(tmp_path: Path, monkeypatch):
    test_workdir = tmp_path / "workdir"
    test_workdir.mkdir()
    run_dir = test_workdir / "run_test_1"
    run_dir.mkdir()
    (run_dir / "sample.py").write_text("print('hello')", encoding="utf-8")

    monkeypatch.setattr("lf.cli.commands.clean.get_workdir_base", lambda: str(test_workdir))

    runner = CliRunner()
    result = runner.invoke(clean_cmd, ["--all", "--dry-run"])
    assert result.exit_code == 0
    assert "SIMULAÇÃO" in result.output
    assert run_dir.exists()


def test_clean_all_deletes_directories(tmp_path: Path, monkeypatch):
    test_workdir = tmp_path / "workdir"
    test_workdir.mkdir()
    run_dir = test_workdir / "run_test_2"
    run_dir.mkdir()
    (run_dir / "file.txt").write_text("data", encoding="utf-8")

    monkeypatch.setattr("lf.cli.commands.clean.get_workdir_base", lambda: str(test_workdir))

    runner = CliRunner()
    result = runner.invoke(clean_cmd, ["--all"])
    assert result.exit_code == 0
    assert "Limpeza concluída" in result.output
    assert not run_dir.exists()
