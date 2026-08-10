"""P0-1: parser do harness detecta erros de coleta do pytest.

Quando o pytest falha na coleta (ModuleNotFoundError, ImportError etc.), a saída
contém linhas 'ERROR ... .py' e um resumo 'N errors in Xs'. Antes do fix, o
parser retornava passed=0/failed=0/total=0 e o QA reportava o genérico
"nenhum teste foi executado". Este teste garante que `errors` seja populado e
que cada erro de coleta conte como falha.
"""

from subprocess import CompletedProcess
from unittest.mock import patch

from lf.pipeline.nodes.qa import _run_harness
from lf.runner.harness.parser import parse_test_output
from lf.runner.harness.runner import TestHarnessRunner

COLETA_FALHANDO = """\
ERROR collecting tests/test_balances.py
tests/test_balances.py:3: in <module>
    from app.services.balance import PaymentProcessor
ModuleNotFoundError: No module named 'app.services.balance'
ERROR tests/test_balances.py - ModuleNotFoundError: No module named 'app.services.balance'
============================ 3 errors in 2.34s ============================
"""


def test_parse_detecta_erro_de_coleta_e_dedup():
    """Linhas 'ERROR collecting' e 'ERROR tests/...' do MESMO módulo viram 1 erro."""
    res = parse_test_output(COLETA_FALHANDO)

    assert res["errors"] == ["tests/test_balances.py"]
    assert res["failed"] >= 1
    assert res["total"] >= 1


def test_parse_conta_erro_do_resumo_sem_linha_error():
    """Resumo '1 error' sem linhas 'ERROR ... .py' ainda conta como falha."""
    res = parse_test_output("============================ 1 error in 0.5s ============================")

    assert res["errors"] == []
    assert res["failed"] >= 1
    assert res["total"] >= 1


def test_parse_dois_modulos_falhando():
    """Dois módulos com erro de coleta → errors com 2 entradas e failed == 2."""
    output = """\
ERROR collecting tests/test_payments.py
ERROR collecting tests/test_notifications.py
============================ 2 errors in 1.10s ============================
"""
    res = parse_test_output(output)

    assert res["errors"] == ["tests/test_payments.py", "tests/test_notifications.py"]
    assert res["failed"] == 2
    assert res["total"] == 2


def test_parse_saida_mista_failed_mais_errors():
    """'5 passed, 1 failed, 2 errors' → failed = 1 + 2 = 3, total = 8."""
    res = parse_test_output("5 passed, 1 failed, 2 errors in 2.3s")

    assert res["passed"] == 5
    assert res["failed"] == 3
    assert res["total"] == 8
    assert res["errors"] == []


def test_runner_popula_errors_e_marca_success_false(tmp_path):
    """Runner-level: returncode != 0 + erro de coleta → errors populado e success False."""
    with patch("lf.runner.harness.runner.subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=2,
            stdout="ERROR collecting tests/test_x.py\nModuleNotFoundError: No module named 'app.services.x'\n"
            "============================ 1 error in 0.80s ============================\n",
            stderr="",
        )
        runner = TestHarnessRunner(command="pytest")
        res = runner.run(cwd=tmp_path)

        assert res.errors == ["tests/test_x.py"]
        assert res.success is False
        assert res.total >= 1
        assert res.failed >= 1


def test_qa_run_harness_repassa_errors(tmp_path, monkeypatch):
    """C4: _run_harness (asdict do TestHarnessResult) expõe `errors` no dict do QA."""
    with patch("lf.runner.harness.runner.subprocess.run") as mock_run:
        mock_run.return_value = CompletedProcess(
            args=[],
            returncode=2,
            stdout="ERROR collecting tests/test_y.py\n============================ 1 error in 0.40s ============================\n",
            stderr="",
        )
        monkeypatch.setattr("lf.pipeline.nodes.qa.os.path.exists", lambda _: True)
        harness_res = _run_harness(str(tmp_path), stack="python", output_dir=str(tmp_path))

        assert harness_res["errors"] == ["tests/test_y.py"]
        assert harness_res["success"] is False
        assert harness_res["failed"] >= 1
