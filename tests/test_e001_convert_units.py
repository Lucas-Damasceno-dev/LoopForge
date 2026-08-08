"""US004 — Conversões comuns de unidades no `lf convert`."""

import re

from click.testing import CliRunner
from lf.cli.commands.convert import convert_cmd

runner = CliRunner()


def _run(*args: str):
    return runner.invoke(convert_cmd, list(args))


def test_us004_km_para_m():
    result = _run("1", "km", "to", "m")
    assert result.exit_code == 0
    assert re.search(r"1000\s*m\b", result.output)


def test_us004_fahrenheit_para_celsius():
    result = _run("32", "f", "to", "c")
    assert result.exit_code == 0
    assert re.search(r"0\s*°?\s?C", result.output)


def test_us004_gb_para_mb():
    result = _run("1", "gb", "to", "mb")
    assert result.exit_code == 0
    assert re.search(r"1024\s*MB", result.output, re.IGNORECASE)


def test_us004_cm_para_m():
    result = _run("100", "cm", "to", "m")
    assert result.exit_code == 0
    assert re.search(r"1\s*m\b", result.output)


def test_us004_kg_para_lb():
    result = _run("10", "kg", "to", "lb")
    assert result.exit_code == 0
    out = result.output
    assert "lb" in out.lower()
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", out)]
    assert numbers, "nenhum valor numérico na saída"
    assert any(abs(n - 22.0462) < 0.01 for n in numbers)


def test_us004_unidade_nao_suportada_lista_unidades_validas():
    result = _run("5", "m", "to", "foo")
    msg = (result.output + result.stderr).lower()
    assert result.exit_code != 0
    assert "suportad" in msg
    assert any(u in msg for u in ("km", "m", "cm", "gb", "kg", "lb"))
