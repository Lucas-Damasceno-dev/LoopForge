"""Fixtures de sessão — hermeticidade dos bancos SQLite de teste.

Causa raiz da flakiness da suíte (``sqlite3/sqlalchemy OperationalError`` em
``test_api*``, ``test_events*``, ``test_parallel_runs*``): os paths de DB são
CWD-relativos por design em ``lf.api.database`` — com ``LF_API_TEST=1`` a
engine aponta para ``.loopforge/test_api.sqlite`` na raiz do repo. Vários
módulos de teste (test_api.py, test_api_coverage.py, test_api_timeline.py,
test_event_envelope.py, test_migration_backfill.py, test_ws_run_filter.py,
etc.) usam o MESMO arquivo compartilhado, deletando/recriando por módulo.
Consequências:

- duas execuções de pytest no mesmo repo colidem no mesmo arquivo
  (``database is locked`` / ``unable to open database file``);
- execuções interrompidas deixam ``-wal``/``-shm`` órfãos que sujam a ordem
  da execução seguinte;
- módulos sem fixture própria (test_serve_no_ui, test_api_mcp,
  test_config_api) podiam tocar o ``.loopforge/telemetry.sqlite`` real.

Fix 100% no lado de teste (nenhum arquivo de produção alterado):

1. ``LF_API_TEST=1`` vale a SESSÃO INTEIRA (autouse por teste) — nenhum
   teste escreve no telemetry.sqlite real via a engine da API;
2. ``pytest_sessionstart`` remove ``.loopforge/test_api.sqlite{-wal,-shm}``
   stale → toda sessão começa com estado zero e a ordem de execução fica
   irrelevante;
3. a fixture autouse re-aplica as env vars em CADA teste, neutralizando os
   ``os.environ.pop("LF_API_TEST", None)`` dos teardowns de módulo.
"""

import contextlib
import os

import pytest

_TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)


@pytest.fixture(autouse=True)
def _lf_test_env():
    """Garante o ambiente de teste da API em todo teste (sessão inteira).

    Roda em todos os testes, inclusive nos módulos sem fixture própria, e
    re-aplica as env vars depois que fixtures de módulo fazem
    ``os.environ.pop`` no teardown — o estado de teste nunca vaza para o
    repositório nem para o teste seguinte.
    """
    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"


def pytest_sessionstart(session):
    """Remove o DB de teste compartilhado stale da raiz do repo.

    WAL/SHM órfãos de execuções interrompidas são o principal vetor de
    poluição de ordem: sem a limpeza, a suíte seguinte herda estado (ou
    locks) da execução anterior. O arquivo é recriado pelas fixtures
    ``setup_test_db`` de cada módulo.
    """
    for path in _TEST_DB_FILES:
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)
