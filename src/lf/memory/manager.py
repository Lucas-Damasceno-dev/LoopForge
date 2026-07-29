"""Memory Manager do LoopForge v6.

Gerencia o histórico de lições aprendidas (lessons.md) e contexto de projetos passados,
permitindo busca por relevância de stack e palavras-chave para recuperar aprendizados.
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path


class MemoryManager:
    """Gerenciador de memória persistente e lições aprendidas do LoopForge."""

    def __init__(self, db_path: str | Path = ".loopforge/memory.sqlite"):
        self.db_path = str(db_path)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Inicializa as tabelas de memória e lições aprendidas no SQLite."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stack TEXT NOT NULL,
                    idea TEXT NOT NULL,
                    lesson_text TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_lessons_stack ON lessons(stack);
            """)
            conn.commit()

    def save_lesson(self, run_id: str, stack: str, idea: str, lesson_text: str) -> None:
        """Salva uma nova lição aprendida no repositório de memória."""
        if not lesson_text or not lesson_text.strip():
            return

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO lessons (run_id, stack, idea, lesson_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, stack.lower().strip(), idea.strip(), lesson_text.strip(), time.time()),
            )
            conn.commit()

    def search_relevant_lessons(self, query: str, stack: str | None = None, limit: int = 3) -> list[dict]:
        """Busca lições aprendidas passadas relevantes por stack e termos da query."""
        keywords = [w.lower().strip() for w in query.split() if len(w) > 3]

        with self._get_connection() as conn:
            if stack:
                rows = conn.execute(
                    "SELECT * FROM lessons WHERE stack = ? ORDER BY created_at DESC LIMIT 20",
                    (stack.lower().strip(),),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM lessons ORDER BY created_at DESC LIMIT 20"
                ).fetchall()

        results = []
        for r in rows:
            text = f"{r['idea']} {r['lesson_text']}".lower()
            score = sum(1 for kw in keywords if kw in text)
            results.append((score, dict(r)))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:limit]]

    def format_lessons_for_prompt(self, lessons: list[dict]) -> str:
        """Formata lições encontradas em bloco Markdown pronto para injeção em prompts."""
        if not lessons:
            return ""

        lines = ["### 🧠 Lições Aprendidas em Execuções Anteriores (Memory Context):"]
        for idx, l in enumerate(lessons, 1):
            stack_badge = f"[{l['stack'].upper()}]"
            lines.append(f"{idx}. {stack_badge} Ideia: '{l['idea']}'")
            lines.append(f"   Lição: {l['lesson_text'].strip()[:250]}...")
        return "\n".join(lines)
