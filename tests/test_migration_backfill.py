"""Migração aditiva de `pipeline_runs` (M-02/ADR-0003 — Fase A1).

Sobre um DB com o schema legado v6.0.0 (sem as colunas `thread_id` /
`parent_run_id`), a migração roda em init_db: detecta colunas via
`PRAGMA table_info`, aplica `ALTER TABLE` e faz backfill de `thread_id`
espelhando a convenção de thread vigente (`run-{id}-task-{substr(id,1,8)}`),
mantendo runs legadas resumíveis. Idempotente: rodar 2x não quebra nem duplica.
"""

import os
import sqlite3
import uuid

import pytest
import pytest_asyncio

from lf.api.database import close_db, init_db

# Schema da tabela pipeline_runs na v6.0.0 (sem thread_id/parent_run_id).
LEGACY_DDL = """
CREATE TABLE pipeline_runs (
    id TEXT PRIMARY KEY,
    idea TEXT NOT NULL,
    stack TEXT,
    status TEXT,
    current_node TEXT,
    logs TEXT,
    duration_seconds REAL,
    created_at DATETIME,
    updated_at DATETIME
)
"""


@pytest_asyncio.fixture(autouse=True)
async def setup_migration_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    yield
    await close_db()


def _read_backfill(db_path: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id, thread_id, parent_run_id FROM pipeline_runs ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_migration_additive_backfill_idempotent():
    os.makedirs(".loopforge", exist_ok=True)
    db_path = ".loopforge/test_api.sqlite"
    run_a = str(uuid.uuid4())
    run_b = str(uuid.uuid4())

    # 1. DB legado v6.0.0 (sem colunas novas) + runs existentes
    conn = sqlite3.connect(db_path)
    conn.execute(LEGACY_DDL)
    conn.execute(
        "INSERT INTO pipeline_runs (id, idea, status) VALUES (?, ?, ?)",
        (run_a, "Run legada A", "completed"),
    )
    conn.execute(
        "INSERT INTO pipeline_runs (id, idea, status) VALUES (?, ?, ?)",
        (run_b, "Run legada B", "failed"),
    )
    conn.commit()
    conn.close()

    # 2. init_db aplica a migração aditiva (create_all + PRAGMA + ALTER + backfill)
    await init_db()

    # 3. Colunas novas presentes via PRAGMA table_info
    conn = sqlite3.connect(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)")}
    finally:
        conn.close()
    assert "thread_id" in cols
    assert "parent_run_id" in cols

    # 4. Backfill espelha a convenção de thread da v6.0.0; parent_run_id NULL
    rows = _read_backfill(db_path)
    assert len(rows) == 2
    for rid, thread_id, parent_run_id in rows:
        assert thread_id == f"run-{rid}-task-{rid[:8]}", (
            f"backfill inesperado para {rid}: {thread_id}"
        )
        assert parent_run_id is None

    # 5. Idempotência: 2ª execução não quebra nem duplica/reescreve
    await close_db()
    await init_db()
    rows = _read_backfill(db_path)
    assert len(rows) == 2, f"idempotência quebrou: {len(rows)} linhas"
    for rid, thread_id, _parent_run_id in rows:
        assert thread_id == f"run-{rid}-task-{rid[:8]}", (
            f"2ª execução reescreveu backfill de {rid}: {thread_id}"
        )
