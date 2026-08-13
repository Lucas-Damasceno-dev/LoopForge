"""Testes de migração aditiva legada da API (colunas degraded em pipeline_runs).

DBs criados antes do campo de degradação não têm as colunas
``degraded``/``degraded_reason`` no ``pipeline_runs`` — a migração
``_ensure_pipeline_runs_degraded_columns`` (app.py) as adiciona via ALTER TABLE
idempotente no startup. Este teste simula a tabela legada e verifica a migração.
"""

import contextlib
import os
import sqlite3

import pytest
import pytest_asyncio

TEST_DB_FILES = (
    ".loopforge/test_api.sqlite",
    ".loopforge/test_api.sqlite-wal",
    ".loopforge/test_api.sqlite-shm",
)

# Schema original (pré-degraded) de pipeline_runs — base legada v6.
_LEGACY_SCHEMA = """
CREATE TABLE pipeline_runs (
    id VARCHAR(36) PRIMARY KEY,
    idea TEXT NOT NULL,
    stack VARCHAR(50) DEFAULT 'python',
    status VARCHAR(20) DEFAULT 'pending',
    current_node VARCHAR(50),
    logs TEXT,
    duration_seconds FLOAT DEFAULT 0.0,
    thread_id VARCHAR(50),
    parent_run_id VARCHAR(36),
    created_at DATETIME,
    updated_at DATETIME
)
"""


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco API SQLite limpo (mesmo padrão de test_api_timeline.py)."""
    from lf.api.database import Base, engine, init_db

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in TEST_DB_FILES:
        with contextlib.suppress(Exception):
            os.remove(f)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    from lf.api.database import close_db

    await close_db()
    for f in TEST_DB_FILES[1:]:
        with contextlib.suppress(Exception):
            os.remove(f)
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


def _pipeline_runs_columns() -> set[str]:
    """Colunas atuais de pipeline_runs no banco de teste (PRAGMA table_info)."""
    conn = sqlite3.connect(".loopforge/test_api.sqlite")
    try:
        return {row[1] for row in conn.execute("PRAGMA table_info(pipeline_runs)")}
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_migracao_legada_adiciona_colunas_degraded():
    """pipeline_runs legada sem degraded → migração adiciona ambas + preserva linha."""
    from lf.api.app import _ensure_pipeline_runs_degraded_columns

    db_path = ".loopforge/test_api.sqlite"
    # Simula DB legado: dropa pipeline_runs e recria no schema antigo (sem colunas).
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("DROP TABLE IF EXISTS pipeline_runs")
        conn.execute(_LEGACY_SCHEMA)
        conn.execute("INSERT INTO pipeline_runs (id, idea) VALUES ('legacy-1', 'antiga')")
        conn.commit()
    finally:
        conn.close()

    assert "degraded" not in _pipeline_runs_columns()
    assert "degraded_reason" not in _pipeline_runs_columns()

    _ensure_pipeline_runs_degraded_columns(db_path)

    cols = _pipeline_runs_columns()
    assert "degraded" in cols
    assert "degraded_reason" in cols

    # Idempotente: rodar de novo não quebra nem duplica colunas.
    _ensure_pipeline_runs_degraded_columns(db_path)
    assert _pipeline_runs_columns() == cols

    # Linha legada sobrevive com defaults (degraded=0, degraded_reason NULL).
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT degraded, degraded_reason FROM pipeline_runs WHERE id = 'legacy-1'").fetchone()
    finally:
        conn.close()
    assert row == (0, None)
