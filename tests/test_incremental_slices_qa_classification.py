"""Testes da classificação de falhas por slice no QA (milestone v7 5.1).

Falhas em ``tests/slices/slice_{NN}/`` pertencem ao slice corrente; qualquer
outro caminho (raiz de tests/, slices anteriores) é regressão; erros livres
sem caminho contam como falha do slice (conservador).
"""

from lf.pipeline.nodes.qa import _classify_slice_failures


def test_classifica_slice_vs_regressao():
    result = {
        "results_by_suite": [
            {
                "failed_tests_details": [
                    {"test_name": "tests/slices/slice_00/test_a.py::test_x"},
                    {"test_name": "tests/slices/slice_00/unit/test_b.py::test_y"},
                    {"test_name": "tests/test_main.py::test_z"},
                    {"test_name": "tests/slices/slice_01/test_prev.py::test_w"},
                ]
            }
        ],
        "errors": ["erro livre sem caminho"],
    }
    slice_failed, regression_failed = _classify_slice_failures(result, 0)
    # 2 paths do slice_00 + 1 erro livre = 3 falhas do slice; 2 de regressão
    assert slice_failed == 3
    assert regression_failed == 2


def test_classifica_slice_01_independe_do_00():
    result = {
        "results_by_suite": [
            {
                "failed_tests_details": [
                    {"test_name": "tests/slices/slice_01/test_c.py::test_q"},
                    {"test_name": "tests/slices/slice_00/test_a.py::test_x"},
                ]
            }
        ],
        "errors": [],
    }
    slice_failed, regression_failed = _classify_slice_failures(result, 1)
    assert slice_failed == 1  # só slice_01
    assert regression_failed == 1  # slice_00 vira regressão


def test_sem_falhas_contagens_zero():
    result = {"results_by_suite": [], "errors": []}
    assert _classify_slice_failures(result, 0) == (0, 0)
