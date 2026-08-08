"""SQLiteLLMCache — Cache semântico de chamadas LLM com SQLite desacoplado."""
import hashlib
import logging
import re
import sqlite3
from pathlib import Path

from ..config.paths import LLM_CACHE_DB_PATH

logger = logging.getLogger(__name__)


def _semantic_normalize_prompt(prompt: str) -> str:
    norm = prompt.lower()
    norm = re.sub(r"\b20\d{2}-\d{2}-\d{2}[tT ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:z|Z)?\b", "", norm)
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


def _connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Abre conexão SQLite com WAL mode e busy_timeout ativados."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except Exception as exc:
        logger.warning("Falha ao acessar cache LLM: %s", exc)
    return conn


class SQLiteLLMCache:
    """Cache semântico de chamadas LLM com SQLite."""

    def __init__(self, db_path: str | Path = LLM_CACHE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with _connect_sqlite(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, prompt: str) -> str | None:
        sem_prompt = _semantic_normalize_prompt(prompt)
        h = hashlib.sha256(sem_prompt.encode()).hexdigest()
        with _connect_sqlite(self.db_path) as conn:
            cur = conn.execute("SELECT response FROM cache WHERE prompt_hash = ?", (h,))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, prompt: str, response: str):
        sem_prompt = _semantic_normalize_prompt(prompt)
        h = hashlib.sha256(sem_prompt.encode()).hexdigest()
        with _connect_sqlite(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (h, response),
            )
            conn.commit()

    def clear(self):
        with _connect_sqlite(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.commit()
