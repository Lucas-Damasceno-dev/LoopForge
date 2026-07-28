from click.testing import CliRunner

from lf.cli.main import main


def test_cli_version(tmp_path):
    """Testa versão mínima do CLI."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(main, ["--version"])
        assert res.exit_code == 0
        assert "loopforge" in res.output.lower()


def test_cli_status_fails_outside_project(tmp_path):
    """Status fora de projeto deve falhar graciosamente."""
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(main, ["status"])
        # Deve falhar sem loopforge.json
        assert res.exit_code != 0
