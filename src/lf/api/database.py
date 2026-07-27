"""Configuração assíncrona do SQLAlchemy para PostgreSQL.

Suporta SQLite como fallback para testes locais sem banco externo.
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from lf.api.config import APISettings


class Base(DeclarativeBase):
    """Base declarativa compartilhada para todos os modelos ORM."""
    pass


def _build_database_url(settings: APISettings) -> str:
    """Converte a URL para async SQLAlchemy.

    Se a variável LF_API_TEST estiver definida, usa SQLite em memória
    para testes sem dependência externa de PostgreSQL.
    """
    if os.getenv("LF_API_TEST"):
        return "sqlite+aiosqlite:///:memory:"
    return settings.database_url


engine = None
session_factory = None


async def init_db(settings: APISettings | None = None) -> None:
    """Inicializa engine e session factory, cria tabelas."""
    global engine, session_factory

    if settings is None:
        settings = APISettings()

    db_url = _build_database_url(settings)
    is_sqlite = db_url.startswith("sqlite")

    kwargs = {"echo": settings.debug}
    if not is_sqlite:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow

    engine = create_async_engine(db_url, **kwargs)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Fecha o engine e libera conexões."""
    global engine, session_factory
    if engine:
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