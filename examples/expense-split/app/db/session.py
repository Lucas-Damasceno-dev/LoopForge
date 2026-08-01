"""Sessão SQLAlchemy e engine do banco de dados."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

class Base(DeclarativeBase):
    """Base declarativa para os modelos ORM."""

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db() -> Generator[Session, None, None]:
    """Abre uma sessão de banco e garante seu fechamento.

    Yields:
        Session: sessão do SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()