"""SQLite Store para o Agentic Interface Registry."""

import json
import os
import sqlite3
from typing import Optional
from registry.store.models import RegistrySchema


class RegistryStore:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.registry_dir = os.path.join(self.repo_root, ".registry")
        os.makedirs(self.registry_dir, exist_ok=True)
        self.db_path = os.path.join(self.registry_dir, "registry.sqlite")
        self.json_path = os.path.join(self.registry_dir, "interfaces.json")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS registry_cache (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    json_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def save(self, schema: RegistrySchema) -> None:
        json_str = schema.model_dump_json(indent=2)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO registry_cache (id, json_data, updated_at) VALUES (1, ?, DATETIME('now'))",
                (json_str,),
            )
            conn.commit()

        with open(self.json_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    def load(self) -> Optional[RegistrySchema]:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return RegistrySchema.model_validate(data)
            except Exception:
                pass

        if not os.path.exists(self.db_path):
            return None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data FROM registry_cache WHERE id = 1")
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return RegistrySchema.model_validate(data)
        return None
