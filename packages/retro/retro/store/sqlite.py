"""SQLite Store para sessões e aprendizados do Agentic Retro."""

import json
import os
import sqlite3
from typing import List, Optional
from retro.store.models import LearningItem, SessionRecord


class RetroStore:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.retro_dir = os.path.join(self.repo_root, ".retro")
        os.makedirs(self.retro_dir, exist_ok=True)
        self.db_path = os.path.join(self.retro_dir, "retro.sqlite")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    goal TEXT,
                    status TEXT,
                    duration_ms REAL,
                    cost REAL,
                    data_json TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    stack TEXT,
                    recommendation TEXT NOT NULL,
                    prompt_override TEXT
                )
            """)
            conn.commit()

    def save_session(self, session: SessionRecord) -> None:
        json_str = session.model_dump_json()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO sessions (session_id, goal, status, duration_ms, cost, data_json) VALUES (?, ?, ?, ?, ?, ?)",
                (session.session_id, session.goal, session.status, session.duration_ms, session.cost, json_str),
            )
            conn.commit()

    def load_session(self, session_id: str) -> Optional[SessionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return SessionRecord.model_validate_json(row[0])
        return None

    def list_sessions(self) -> List[SessionRecord]:
        sessions = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM sessions ORDER BY rowid DESC")
            for row in cursor.fetchall():
                try:
                    sessions.append(SessionRecord.model_validate_json(row[0]))
                except Exception:
                    pass
        return sessions

    def add_learnings(self, learnings: List[LearningItem]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for l in learnings:
                cursor.execute(
                    "INSERT INTO learnings (category, stack, recommendation, prompt_override) VALUES (?, ?, ?, ?)",
                    (l.category, l.stack, l.recommendation, l.prompt_override),
                )
            conn.commit()

    def list_learnings(self, stack: Optional[str] = None) -> List[LearningItem]:
        learnings = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            if stack:
                cursor.execute("SELECT category, stack, recommendation, prompt_override FROM learnings WHERE stack = ?", (stack,))
            else:
                cursor.execute("SELECT category, stack, recommendation, prompt_override FROM learnings")
            for row in cursor.fetchall():
                learnings.append(
                    LearningItem(
                        category=row[0],
                        stack=row[1],
                        recommendation=row[2],
                        prompt_override=row[3],
                    )
                )
        return learnings
