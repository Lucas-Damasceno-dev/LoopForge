"""Factories de checkpointer LangGraph para a ADE.

Trajectories assíncronas em `.loopforge/trajectories.db` com modo WAL explícito
garantido na abertura (antes do `setup()`), para evitar travamentos de
leitura/escrita concorrentes durante chamadas da API.
"""

import sqlite3
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


def create_async_checkpointer(path: str | Path) -> AsyncSqliteSaver:
    """Cria um checkpointer assíncrono com WAL garantido antes do setup.

    O modo WAL é persistente no arquivo do banco: abrimos uma conexão síncrona
    na factory e aplicamos ``PRAGMA journal_mode=WAL`` antes de qualquer
    operação do saver, garantindo que o gate ``_wal_mode == "wal"`` passe
    imediatamente após a criação.
    """
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # WAL explícito na abertura (antes do setup) — leituras/escritas concorrentes
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    return AsyncSqliteSaver(conn=aiosqlite.connect(str(db_path)))


def create_sync_checkpointer(path: str | Path) -> SqliteSaver:
    """Cria um checkpointer síncrono (compat com o caminho CLI legado)."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return SqliteSaver(conn=conn)
