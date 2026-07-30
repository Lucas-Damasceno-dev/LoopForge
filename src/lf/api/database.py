"""Configuração assíncrona do SQLAlchemy para o Banco Único do LoopForge.

Unifica a persistência REST e Telemetria em `.loopforge/telemetry.sqlite`.
"""
import os
from collections.abc import AsyncGenerator

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

    kwargs = {"echo": settings.debug}
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
    from lf.api import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)



async def close_db() -> None:
    """Fecha o engine e libera conexões."""
    global engine, session_factory
    if engine:
        try:
            await engine.dispose()
        except Exception:
            pass
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
