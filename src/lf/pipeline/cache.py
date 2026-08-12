"""SQLiteLLMCache — Cache semântico de chamadas LLM com SQLite desacoplado."""

import hashlib
import logging
import re
import sqlite3
from pathlib import Path

from ..config.paths import LLM_CACHE_DB_PATH

logger = logging.getLogger(__name__)

# TTL do cache: entradas mais velhas que isso são tratadas como miss (get) e
# podadas no próximo insert (set). Evita resposta stale e crescimento infinito.
_CACHE_TTL_DAYS = 30


def _semantic_normalize_prompt(prompt: str) -> str:
    norm = prompt.lower()
    norm = re.sub(r"\b20\d{2}-\d{2}-\d{2}[tT ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:z|Z)?\b", "", norm)
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


def _cache_key(prompt: str, model: str | None = None, temperature: float | None = None) -> str:
    """Chave SHA256 do prompt normalizado + modelo + temperatura.

    model/temperature None (chamada legada) → chave só do prompt, mantendo o
    comportamento antigo. Com modelo informado, o mesmo prompt com modelos
    diferentes não colide mais (antes reusava resposta errada entre modelos).
    """
    sem_prompt = _semantic_normalize_prompt(prompt)
    model_part = model or ""
    temp_part = "" if temperature is None else str(temperature)
    return hashlib.sha256(f"{model_part}|{temp_part}|{sem_prompt}".encode()).hexdigest()


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
            # Compat com DB existente: garante created_at em bancos criados antes
            # do TTL (defensivo — CREATE IF NOT EXISTS não altera schema antigo).
            cols = {row[1] for row in conn.execute("PRAGMA table_info(cache)")}
            if "created_at" not in cols:
                conn.execute("ALTER TABLE cache ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    hits INTEGER NOT NULL DEFAULT 0,
                    misses INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute("INSERT OR IGNORE INTO cache_stats (id, hits, misses) VALUES (1, 0, 0)")
            conn.commit()

    def get(self, prompt: str, model: str | None = None, temperature: float | None = None) -> str | None:
        h = _cache_key(prompt, model, temperature)
        with _connect_sqlite(self.db_path) as conn:
            # TTL: rows com created_at anterior a _CACHE_TTL_DAYS contam como miss
            cur = conn.execute(
                "SELECT response FROM cache WHERE prompt_hash = ? AND created_at > datetime('now', ?)",
                (h, f"-{_CACHE_TTL_DAYS} days"),
            )
            row = cur.fetchone()
            if row:
                conn.execute("UPDATE cache_stats SET hits = hits + 1 WHERE id = 1")
                conn.commit()
                return row[0]
            conn.execute("UPDATE cache_stats SET misses = misses + 1 WHERE id = 1")
            conn.commit()
            return None

    def stats(self) -> dict:
        """Retorna métricas de hit/miss do cache: hits, misses, total e hit_rate."""
        with _connect_sqlite(self.db_path) as conn:
            row = conn.execute("SELECT hits, misses FROM cache_stats WHERE id = 1").fetchone()
        hits, misses = (int(row[0]), int(row[1])) if row else (0, 0)
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "total": total,
            "hit_rate": (hits / total) if total > 0 else 0.0,
        }

    def set(
        self,
        prompt: str,
        response: str,
        model: str | None = None,
        temperature: float | None = None,
    ):
        h = _cache_key(prompt, model, temperature)
        with _connect_sqlite(self.db_path) as conn:
            # Eviction leve: poda entradas expiradas a cada insert (sem apagar tudo)
            conn.execute(
                "DELETE FROM cache WHERE created_at < datetime('now', ?)",
                (f"-{_CACHE_TTL_DAYS} days",),
            )
            conn.execute(
                "INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (h, response),
            )
            conn.commit()

    def clear(self):
        with _connect_sqlite(self.db_path) as conn:
            conn.execute("DELETE FROM cache")
            conn.execute("DELETE FROM cache_stats")
            conn.execute("INSERT INTO cache_stats (id, hits, misses) VALUES (1, 0, 0)")
            conn.commit()
