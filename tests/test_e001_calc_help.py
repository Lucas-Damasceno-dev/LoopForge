"""US007 — Ajuda e documentação embutida na CLI."""

import re

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

from lf.cli.main import main

runner = CliRunner()


def test_us007_calc_help_lista_opcoes_e_exemplos():
    result = runner.invoke(calc_cmd, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.output
    assert "Options" in result.output
    assert "exemplo" in result.output.lower() or '"2 + 3"' in result.output


def test_us007_help_principal_lista_todos_comandos():
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "calc" in result.output
    assert "convert" in result.output


def test_us007_calc_sem_argumentos_mostra_exemplo_de_uso():
    result = runner.invoke(calc_cmd, [])
    assert result.exit_code != 0
    assert "Usage" in result.output or "exemplo" in result.output.lower() or "uso" in result.output.lower()


def test_us007_calc_version_mostra_versao_instalada():
    result = runner.invoke(calc_cmd, ["--version"])
    assert result.exit_code == 0
    assert re.search(r"\d+\.\d+\.\d+", result.output)
