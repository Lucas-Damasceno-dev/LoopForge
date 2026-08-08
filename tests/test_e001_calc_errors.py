"""US006 — Tratamento de erros de entrada no `lf calc`."""

import re

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()

POSITION = re.compile(r"posi[çc][ãa]o|índice|caractere|na\s+posi")


def _message(result) -> str:
    return (result.output + result.stderr).lower()


def test_us006_expressao_incompleta_indica_posicao_e_problema():
    result = runner.invoke(calc_cmd, ["2 +"])
    assert result.exit_code != 0
    msg = _message(result)
    assert POSITION.search(msg), f"erro deve indicar posição: {msg!r}"
    assert any(k in msg for k in ("incompleta", "esperad", "operando", "fim da expressão", "operador"))


def test_us006_entrada_nao_numerica_e_invalida():
    result = runner.invoke(calc_cmd, ["abc"])
    assert result.exit_code != 0
    assert "inválid" in _message(result)


def test_us006_divisao_por_zero():
    result = runner.invoke(calc_cmd, ["10 / 0"])
    assert result.exit_code != 0
    msg = _message(result)
    assert "divisão por zero" in msg or ("divisão" in msg and "zero" in msg)


def test_us006_parentese_nao_fechado():
    result = runner.invoke(calc_cmd, ["(2 + 3"])
    assert result.exit_code != 0
    msg = _message(result)
    assert "parêntese" in msg
    assert any(k in msg for k in ("faltante", "faltando", "não fechad", "nao fechad", "fechamento"))
