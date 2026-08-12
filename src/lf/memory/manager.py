"""Memory Manager do LoopForge v6.

Gerencia o histórico de lições aprendidas (lessons.md) e contexto de projetos passados,
permitindo busca por relevância de stack e palavras-chave para recuperar aprendizados.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from ..config.paths import TELEMETRY_DB_PATH


def cross_project_enabled(config=None) -> bool:
    """True quando a memória cross-project está ligada (AdeConfig.memory.cross_project).

    Fonte única de verdade para os nós do pipeline e endpoints de memória:
    quando ativa, a busca de lições ignora o filtro de stack.
    """
    from ..config.loader import load_ade_config

    cfg = config if config is not None else load_ade_config()
    return bool(getattr(getattr(cfg, "memory", None), "cross_project", False))


class MemoryManager:
    """Gerenciador de memória persistente e lições aprendidas do LoopForge."""

    def __init__(self, db_path: str | Path = TELEMETRY_DB_PATH):
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

    def save_lesson(self, run_id: str, stack: str, idea: str, lesson_text: str) -> dict | None:
        """Salva uma nova lição aprendida e retorna a lição criada (None se vazia).

        A API de memória reutiliza este método no POST /lessons; por isso passa a
        devolver o registro completo recém-inserido (id gerado no INSERT).
        """
        if not lesson_text or not lesson_text.strip():
            return None

        with self._get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO lessons (run_id, stack, idea, lesson_text, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, stack.lower().strip(), idea.strip(), lesson_text.strip(), time.time()),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM lessons WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row) if row else None

    def get_lesson(self, lesson_id: int) -> dict | None:
        """Retorna uma lição pelo id, ou None se não existir."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        return dict(row) if row else None

    def list_lessons(
        self,
        stack: str | None = None,
        limit: int = 50,
        cross_project: bool = False,
    ) -> list[dict]:
        """Lista as lições mais recentes, opcionalmente filtradas por stack.

        Ordenadas por created_at DESC (mais recentes primeiro). O valor de stack
        é normalizado em minúsculas antes do filtro. Com ``cross_project=True``
        o filtro de stack é ignorado (todas as stacks entram no contexto).
        """
        with self._get_connection() as conn:
            if stack and not cross_project:
                rows = conn.execute(
                    "SELECT * FROM lessons WHERE stack = ? ORDER BY created_at DESC LIMIT ?",
                    (stack.lower().strip(), limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM lessons ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def update_lesson(
        self,
        lesson_id: int,
        *,
        stack: str | None = None,
        idea: str | None = None,
        lesson_text: str | None = None,
    ) -> dict | None:
        """Atualiza apenas os campos informados de uma lição.

        Retorna a lição atualizada, ou None se o id não existir. Com todos os
        campos ausentes, devolve a lição inalterada (PATCH vazio é idempotente).
        """
        fields: list[str] = []
        params: list[str] = []
        if stack is not None:
            fields.append("stack = ?")
            params.append(stack.lower().strip())
        if idea is not None:
            fields.append("idea = ?")
            params.append(idea.strip())
        if lesson_text is not None:
            fields.append("lesson_text = ?")
            params.append(lesson_text.strip())
        if not fields:
            return self.get_lesson(lesson_id)

        params.append(str(lesson_id))
        with self._get_connection() as conn:
            cur = conn.execute(
                f"UPDATE lessons SET {', '.join(fields)} WHERE id = ?",
                params,
            )
            conn.commit()
        if cur.rowcount == 0:
            return None
        return self.get_lesson(lesson_id)

    def delete_lesson(self, lesson_id: int) -> bool:
        """Remove uma lição pelo id. Retorna True se algum registro foi removido."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
            conn.commit()
        return cur.rowcount > 0

    def search_relevant_lessons(
        self,
        query: str,
        stack: str | None = None,
        limit: int = 3,
        only_relevant: bool = False,
        cross_project: bool = False,
    ) -> list[dict]:
        """Busca lições aprendidas passadas relevantes por stack e termos da query.

        Com ``only_relevant=True`` (API de memória), descarta lições com score 0
        (nenhuma palavra-chave encontrada) — o pipeline de execução mantém o
        comportamento atual (default False) e recebe contexto por stack mesmo
        sem match de palavras-chave. Com ``cross_project=True`` (ROADMAP 3.1),
        o filtro de stack é ignorado — a busca varre todas as stacks.
        """
        keywords = [w.lower().strip() for w in query.split() if len(w) > 3]

        with self._get_connection() as conn:
            if stack and not cross_project:
                rows = conn.execute(
                    "SELECT * FROM lessons WHERE stack = ? ORDER BY created_at DESC LIMIT 20",
                    (stack.lower().strip(),),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM lessons ORDER BY created_at DESC LIMIT 20").fetchall()

        results = []
        for r in rows:
            text = f"{r['idea']} {r['lesson_text']}".lower()
            score = sum(1 for kw in keywords if kw in text)
            results.append((score, dict(r)))

        if only_relevant:
            results = [item for item in results if item[0] > 0]

        results.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in results[:limit]]

    def format_lessons_for_prompt(self, lessons: list[dict]) -> str:
        """Formata lições encontradas em bloco Markdown pronto para injeção em prompts."""
        if not lessons:
            return ""

        lines = ["### 🧠 Lições Aprendidas em Execuções Anteriores (Memory Context):"]
        for idx, item in enumerate(lessons, 1):
            stack_badge = f"[{item['stack'].upper()}]"
            lines.append(f"{idx}. {stack_badge} Ideia: '{item['idea']}'")
            lines.append(f"   Lição: {item['lesson_text'].strip()[:250]}...")
        return "\n".join(lines)
