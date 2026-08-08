"""US001 — Operações aritméticas básicas na CLI (`lf calc`)."""

import re

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()


def _run(expr: str):
    return runner.invoke(calc_cmd, [expr])


def test_us001_soma_2_mais_3():
    result = _run("2 + 3")
    assert result.exit_code == 0
    assert result.output.strip() == "5"


def test_us001_subtracao_10_menos_4():
    result = _run("10 - 4")
    assert result.exit_code == 0
    assert result.output.strip() == "6"


def test_us001_multiplicacao_6_vezes_7():
    result = _run("6 * 7")
    assert result.exit_code == 0
    assert result.output.strip() == "42"


def test_us001_divisao_20_por_4():
    result = _run("20 / 4")
    assert result.exit_code == 0
    assert result.output.strip() == "5"


def test_us001_divisao_10_por_3_com_precisao_decimal():
    result = _run("10 / 3")
    assert result.exit_code == 0
    out = result.output.strip()
    assert re.fullmatch(r"3\.3{9,}\d*", out), f"precisão decimal insuficiente: {out!r}"
