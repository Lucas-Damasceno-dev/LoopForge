from pathlib import Path
import sqlite3
from typing import Any


class TelemetryStore:
    def __init__(self, db_path: str | Path = ".loopforge/telemetry.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    node TEXT NOT NULL,
                    status TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0.0,
                    cost_usd REAL DEFAULT 0.0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def log_event(self, session_id: str, task_id: str, node: str, status: str, duration: float = 0.0, cost: float = 0.0):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (session_id, task_id, node, status, duration_seconds, cost_usd)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, task_id, node, status, duration, cost),
            )

    def fetch_all(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute("SELECT * FROM runs ORDER BY id DESC")
            return [dict(row) for row in cur.fetchall()]
