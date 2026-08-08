"""US003 — Cálculos percentuais no `lf calc`."""

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()


def _run(expr: str):
    return runner.invoke(calc_cmd, [expr])


def test_us003_percentual_de_200():
    result = _run("15% de 200")
    assert result.exit_code == 0
    assert result.output.strip() == "30"


def test_us003_aumento_percentual():
    result = _run("200 + 15%")
    assert result.exit_code == 0
    assert result.output.strip() == "230"


def test_us003_desconto_percentual():
    result = _run("200 - 15%")
    assert result.exit_code == 0
    assert result.output.strip() == "170"


def test_us003_razao_percentual():
    result = _run("50 de 200 %")
    assert result.exit_code == 0
    assert result.output.strip() == "25%"
