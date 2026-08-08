"""A2/M-07 (Fase A, n6): runs CLI (`lf run --mock`) viram linhas em pipeline_runs.

O dispatcher é o WRITER CANÔNICO de pipeline_runs: grava via sqlite3 direto no
MESMO ``.loopforge/telemetry.sqlite`` do ``_record_decision`` (sem depender do
create_all da API — a tabela pode nem existir em runs CLI puras). Runs CLI
(thread ``project-task-1``) recebem um uuid NOVO como id e o thread real fica na
coluna ``thread_id``; o journal de eventos fica chaveado pelo MESMO id da linha,
então GET /api/runs (M-07) e GET /runs/{id}/events enxergam runs CLI.

NÃO seta LF_API_TEST — sob LF_API_TEST a API escreveria em
.loopforge/test_api.sqlite enquanto o dispatcher grava telemetry.sqlite. Em
produção ambos usam sqlite+aiosqlite:///.loopforge/telemetry.sqlite (mesmo
padrão endurecido de test_hitl_remote_e2e, com chdir em tmp_path).
"""

import asyncio
import contextlib
import sqlite3
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher

CLI_IDEA = "Build CLI feature"
CLI_THREAD = "project-task-1"


@pytest.fixture(autouse=True)
def setup_cli_telemetry(tmp_path, monkeypatch):
    """Banco único em tmp_path (sem LF_API_TEST) + limpeza endurecida WAL/SHM."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LF_API_TEST", raising=False)
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    asyncio.run(init_db())
    yield
    asyncio.run(close_db())
    # Contenção sqlite (outras tarefas podem rodar pytest no mesmo dir em
    # paralelo): remove artefatos WAL/SHM para não vazar estado entre testes.
    for artifact in tmp_path.glob(".loopforge/*.sqlite-wal"):
        with contextlib.suppress(OSError):
            artifact.unlink()
    for artifact in tmp_path.glob(".loopforge/*.sqlite-shm"):
        with contextlib.suppress(OSError):
            artifact.unlink()


def _run_dispatch(project_id: str = "project") -> dict:
    """Executa a pipeline mock do jeito que a CLI faz (project_id padrão)."""
    task = TaskSchema(id="task-1", title=CLI_IDEA, agent_id="cpo", stack="python")
    dispatcher = TaskDispatcher(mock_llm=True)
    return dispatcher.dispatch(task, project_id=project_id)


def _pipeline_rows(thread_id: str = CLI_THREAD) -> list[tuple]:
    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        return conn.execute(
            "SELECT id, status, thread_id FROM pipeline_runs WHERE thread_id = ?",
            (thread_id,),
        ).fetchall()
    finally:
        conn.close()


def test_cli_dispatch_writes_pipeline_run_row():
    """(a) Dispatch mock (padrão CLI) cria 1 linha completed com id uuid e thread salvo."""
    result = _run_dispatch()
    assert not result.get("error"), result.get("error")

    rows = _pipeline_rows()
    assert len(rows) == 1, f"esperado 1 linha em pipeline_runs, achou {rows}"
    run_id, status, thread_id = rows[0]
    assert status == "completed", status
    assert thread_id == CLI_THREAD, thread_id
    # id é uuid (str(uuid.uuid4())) — parseia sem erro
    uuid.UUID(run_id)


def test_cli_dispatch_twice_no_duplicated_rows():
    """(a) 2 dispatches = 2 linhas com ids distintos (upsert idempotente por dispatch)."""
    _run_dispatch()
    _run_dispatch()

    rows = _pipeline_rows()
    # Cada dispatch gera um uuid NOVO (thread CLI não deriva o id da run),
    # então 2 dispatches = 2 linhas; cada id aparece EXATAMENTE 1x (o mesmo
    # dispatch não duplica running→completed).
    assert len(rows) == 2, f"esperado 2 linhas, achou {rows}"
    ids = [row[0] for row in rows]
    assert len(set(ids)) == 2, f"ids duplicados após 2 dispatches: {ids}"
    assert {row[1] for row in rows} == {"completed"}, rows


def test_cli_events_journaled_with_pipeline_run_id():
    """(b) Journal de eventos usa run_id = id da linha (pipeline_started/finished)."""
    _run_dispatch()

    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        run_row = conn.execute("SELECT id FROM pipeline_runs WHERE thread_id = ?", (CLI_THREAD,)).fetchone()
        assert run_row, "linha em pipeline_runs ausente"
        run_id = run_row[0]
        event_types = {
            row[0] for row in conn.execute("SELECT event_type FROM events WHERE run_id = ?", (run_id,)).fetchall()
        }
    finally:
        conn.close()

    assert "pipeline_started" in event_types, event_types
    assert "pipeline_finished" in event_types, event_types


def test_cli_run_shows_in_api_runs_list():
    """(c) GET /api/runs enxerga a run CLI (mesmo DB, sem LF_API_TEST)."""
    _run_dispatch()

    conn = sqlite3.connect(".loopforge/telemetry.sqlite")
    try:
        run_row = conn.execute("SELECT id, status FROM pipeline_runs WHERE thread_id = ?", (CLI_THREAD,)).fetchone()
        assert run_row, "linha em pipeline_runs ausente"
        run_id, db_status = run_row
    finally:
        conn.close()

    app = create_app()

    async def _check():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.get("/api/runs")

    resp = asyncio.run(_check())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = {item["id"]: item for item in data["items"]}
    assert run_id in items, f"run CLI {run_id} ausente em GET /api/runs: {list(items)}"
    item = items[run_id]
    assert item["status"] == db_status == "completed", item["status"]
    assert item["idea"] == CLI_IDEA, item["idea"]
