"""US002 — Precedência de operadores e parênteses no `lf calc`."""

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()


def _run(expr: str):
    return runner.invoke(calc_cmd, [expr])


def test_us002_multiplicacao_tem_precedencia_sobre_soma():
    result = _run("2 + 3 * 4")
    assert result.exit_code == 0
    assert result.output.strip() == "14"


def test_us002_parenteses_alteram_precedencia():
    result = _run("(2 + 3) * 4")
    assert result.exit_code == 0
    assert result.output.strip() == "20"


def test_us002_parenteses_aninhados():
    result = _run("2 + 3 * (4 - 1)")
    assert result.exit_code == 0
    assert result.output.strip() == "11"
