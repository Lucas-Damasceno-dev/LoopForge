"""US005 — Saída legível e exit codes no terminal (`lf calc`)."""

import re

from click.testing import CliRunner
from lf.cli.commands.calc import calc_cmd

runner = CliRunner()

GREEN = re.compile(r"\x1b\[(?:0;)?(?:32|92)m")
RED = re.compile(r"\x1b\[(?:0;)?(?:31|91)m")


def test_us005_saida_mostra_apenas_o_resultado():
    result = runner.invoke(calc_cmd, ["2 + 2"])
    assert result.exit_code == 0
    assert result.output.strip() == "4"


def test_us005_exit_code_zero_no_sucesso():
    result = runner.invoke(calc_cmd, ["2 + 2"])
    assert result.exit_code == 0


def test_us005_erro_em_stderr_com_exit_code_nao_zero():
    result = runner.invoke(calc_cmd, ["2 ++"])
    assert result.exit_code != 0
    assert result.stderr.strip() != ""


def test_us005_resultado_verde_e_erro_vermelho():
    ok = runner.invoke(calc_cmd, ["2 + 2"], color=True)
    assert GREEN.search(ok.output)

    err = runner.invoke(calc_cmd, ["2 +"], color=True)
    assert RED.search(err.output + err.stderr)
