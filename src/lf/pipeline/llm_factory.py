import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Optional

from langchain_core.language_models.fake import FakeListLLM


class SQLiteLLMCache:
    def __init__(self, db_path: str | Path = ".loopforge/llm_cache.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def get(self, prompt: str) -> Optional[str]:
        h = hashlib.sha256(prompt.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT response FROM cache WHERE prompt_hash = ?", (h,))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, prompt: str, response: str):
        h = hashlib.sha256(prompt.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)",
                (h, response),
            )


def get_llm(provider: str = "google", model_name: str = "gemini-1.5-flash", temperature: float = 0.2) -> Any:
    """Returns an LLM instance based on provider string."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Fallback to FakeListLLM for offline/mock environments
        responses = [
            json.dumps({"title": "Mock Epic", "id": "epic-1", "user_stories": ["us-1"]}),
            json.dumps({"id": "us-1", "title": "Mock User Story", "acceptance_criteria": ["Given x when y then z"]}),
            "# Tech Spec\n\nMock technical specification.",
            "Mock code implementation response.",
            json.dumps({"total_tests": 1, "passed": 1, "failed": 0}),
        ]
        return FakeListLLM(responses=responses * 10)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=temperature)
    except Exception:
        responses = ["Mock LLM response"] * 100
        return FakeListLLM(responses=responses)


def get_llm_client(provider: str = "google", model_name: str = "gemini-2.0-flash", temperature: float = 0.3) -> Any:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        # Fallback to FakeListLLM for offline/mock environments
        responses = [
            json.dumps({"title": "Mock Epic", "id": "epic-1", "user_stories": ["us-1"]}),
            json.dumps({"id": "us-1", "title": "Mock User Story", "acceptance_criteria": ["Given x when y then z"]}),
            "# Tech Spec\n\nMock technical specification.",
            "Mock code implementation response.",
            json.dumps({"total_tests": 1, "passed": 1, "failed": 0}),
        ]
        return FakeListLLM(responses=responses * 10)

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key, temperature=temperature)
    except Exception:
        responses = ["Mock LLM response"] * 100
        return FakeListLLM(responses=responses)
