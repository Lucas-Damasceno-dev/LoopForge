"""US010 — Entrada interativa e em pipeline no `lf calc`."""

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()


def test_us010_entrada_pipeline_via_stdin():
    result = runner.invoke(calc_cmd, [], input="4 * 5\n")
    assert result.exit_code == 0
    assert "20" in result.output


def test_us010_modo_interativo_mantem_prompt():
    result = runner.invoke(calc_cmd, [], input="6 * 7\nsair\n")
    assert result.exit_code == 0
    assert "42" in result.output
    assert result.output.count(">") >= 2


def test_us010_sair_encerra_com_exit_code_zero():
    result = runner.invoke(calc_cmd, [], input="sair\n")
    assert result.exit_code == 0


def test_us010_multiplas_expressoes_em_linhas_separadas():
    result = runner.invoke(calc_cmd, ["1 + 2", "3 + 4"])
    assert result.exit_code == 0
    lines = [ln for ln in result.output.strip().splitlines() if ln.strip()]
    assert lines == ["3", "7"]
