"""Configuração assíncrona do SQLAlchemy para o Banco Único do LoopForge.

Unifica a persistência REST e Telemetria em `.loopforge/telemetry.sqlite`.
"""

import contextlib
import os
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from lf.api.config import APISettings


class Base(DeclarativeBase):
    """Base declarativa compartilhada para todos os modelos ORM."""


def _build_database_url(settings: APISettings) -> str:
    """Retorna URL do banco. Se LF_API_TEST estiver setado, usa SQLite de teste."""
    if os.getenv("LF_API_TEST"):
        os.makedirs(".loopforge", exist_ok=True)
        return "sqlite+aiosqlite:///.loopforge/test_api.sqlite"
    return settings.database_url


engine = None
session_factory = None


async def init_db(settings: APISettings | None = None) -> None:
    """Inicializa engine e session factory, cria tabelas no banco único."""
    global engine, session_factory

    if settings is None:
        settings = APISettings()

    db_url = _build_database_url(settings)
    is_sqlite = db_url.startswith("sqlite")

    if is_sqlite and not os.getenv("LF_API_TEST"):
        os.makedirs(".loopforge", exist_ok=True)

    kwargs: dict[str, Any] = {"echo": settings.debug}
    if not is_sqlite:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow

    engine = create_async_engine(db_url, **kwargs)

    if is_sqlite:
        from sqlalchemy import event

        @event.listens_for(engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA busy_timeout=5000")
            except Exception:
                pass
            finally:
                cursor.close()

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Garante que todos os modelos ORM estejam registrados no Base.metadata
    from lf.api import events, models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Semeadura da tabela de sequência de eventos (event_seq): runs legadas
        # com eventos já persistidos continuam com seq contíguo (o próximo
        # publish segue do MAX atual). Idempotente via ON CONFLICT DO NOTHING.
        from sqlalchemy import text

        await conn.execute(
            text(
                "INSERT INTO event_seq (run_id, last_seq) "
                "SELECT run_id, MAX(seq) FROM events GROUP BY run_id "
                "ON CONFLICT (run_id) DO NOTHING"
            )
        )
        # Migração aditiva de pipeline_runs (ADR-0003/M-02): colunas
        # thread_id/parent_run_id + backfill. PRAGMA table_info é SQLite-only.
        if is_sqlite:
            await _apply_pipeline_runs_additive_migration(conn)


async def _apply_pipeline_runs_additive_migration(conn) -> None:
    """Migração aditiva de `pipeline_runs` (ADR-0003/M-02).

    Adiciona as colunas `thread_id` e `parent_run_id` quando ausentes (detecção
    via PRAGMA table_info) e faz backfill de `thread_id` espelhando a convenção
    de thread vigente na v6.0.0 (`run-{id}-task-{substr(id,1,8)}`), para runs
    legadas continuarem resumíveis pelo próprio thread real em trajectories.db.

    Importante: em DBs onde as colunas JÁ existem (schema novo) a função é
    read-only — o backfill só roda quando a migração acabou de adicionar as
    colunas. Isso mantém o init_db sem transações de escrita desnecessárias
    (o create_all de tabelas existentes é read-only), evitando sujar o WAL do
    SQLite em fixtures que apagam o arquivo do banco entre testes. Idempotente:
    rodar N vezes é seguro e não duplica nem reescreve backfills.
    """
    from sqlalchemy import text

    result = await conn.exec_driver_sql("PRAGMA table_info(pipeline_runs)")
    columns = {row[1] for row in result.fetchall()}

    migrated = False
    if "thread_id" not in columns:
        await conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN thread_id VARCHAR(50)"))
        migrated = True
    if "parent_run_id" not in columns:
        await conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN parent_run_id VARCHAR(36)"))
        migrated = True

    if migrated:
        await conn.execute(
            text(
                "UPDATE pipeline_runs SET thread_id = 'run-' || id || '-task-' || substr(id, 1, 8) "
                "WHERE thread_id IS NULL"
            )
        )


async def close_db() -> None:
    """Fecha o engine e libera conexões."""
    global engine, session_factory
    if engine:
        with contextlib.suppress(Exception):
            await engine.dispose()
    engine = None
    session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Provider de sessão para injeção de dependência do FastAPI."""
    if session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
