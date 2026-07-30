"""SQLite Storage e cache incremental para o Codebase Genome."""

import json
import os
import sqlite3
from typing import Dict, Optional
from .models import Genome


class GenomeStore:
    def __init__(self, repo_root: str):
        self.repo_root = os.path.abspath(repo_root)
        self.genome_dir = os.path.join(self.repo_root, ".genome")
        os.makedirs(self.genome_dir, exist_ok=True)
        self.db_path = os.path.join(self.genome_dir, "genome.sqlite")
        self.json_path = os.path.join(self.genome_dir, "genome.json")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS genome_cache (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    json_data TEXT NOT NULL,
                    generated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_hashes (
                    file_path TEXT PRIMARY KEY,
                    hash TEXT NOT NULL,
                    mtime REAL NOT NULL
                )
            """)
            conn.commit()

    def save_genome(self, genome: Genome) -> None:
        json_str = genome.model_dump_json(indent=2)
        # Salva tanto no SQLite quanto em genome.json para interoperabilidade rápida
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO genome_cache (id, json_data, generated_at) VALUES (1, ?, ?)",
                (json_str, genome.generated_at),
            )
            conn.commit()

        with open(self.json_path, "w", encoding="utf-8") as f:
            f.write(json_str)

    def load_genome(self) -> Optional[Genome]:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return Genome.model_validate(data)
            except Exception:
                pass

        if not os.path.exists(self.db_path):
            return None

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT json_data FROM genome_cache WHERE id = 1")
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return Genome.model_validate(data)
        return None

    def get_file_hashes(self) -> Dict[str, str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path, hash FROM file_hashes")
            return {row[0]: row[1] for row in cursor.fetchall()}

    def update_file_hash(self, file_path: str, file_hash: str, mtime: float) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO file_hashes (file_path, hash, mtime) VALUES (?, ?, ?)",
                (file_path, file_hash, mtime),
            )
            conn.commit()
