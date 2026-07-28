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


DEFAULT_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
DEFAULT_OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash:free")



def call_openrouter_api(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    temperature: float = 0.2,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> str:
    """Realiza uma chamada direta à API do OpenRouter via httpx usando o modelo Ling-3.0 Flash."""
    import httpx
    key = api_key or os.environ.get("OPENROUTER_API_KEY") or DEFAULT_OPENROUTER_KEY
    if not key:
        raise ValueError("OPENROUTER_API_KEY não foi configurada.")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://loopforge.dev",
        "X-Title": "LoopForge AI Engine",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    if response.status_code != 200:
        raise RuntimeError(f"OpenRouter API error ({response.status_code}): {response.text}")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"OpenRouter API retornou resposta vazia: {data}")

    return choices[0]["message"]["content"]


def get_llm(provider: str = "openrouter", model_name: str = DEFAULT_OPENROUTER_MODEL, temperature: float = 0.2) -> Any:
    """Returns an LLM instance or runner based on provider string."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or DEFAULT_OPENROUTER_KEY
    if provider == "openrouter" or api_key:
        return lambda prompt: call_openrouter_api(prompt, model=model_name, temperature=temperature, api_key=api_key)

    api_key_gemini = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key_gemini:
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
        return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key_gemini, temperature=temperature)
    except Exception:
        responses = ["Mock LLM response"] * 100
        return FakeListLLM(responses=responses)


def get_llm_client(provider: str = "openrouter", model_name: str = DEFAULT_OPENROUTER_MODEL, temperature: float = 0.3) -> Any:
    import warnings
    warnings.warn("get_llm_client is deprecated, use get_llm() instead", DeprecationWarning, stacklevel=2)
    return get_llm(provider=provider, model_name=model_name, temperature=temperature)

