import hashlib
import json
import os
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

from langchain_core.language_models.fake import FakeListLLM

DEFAULT_OPENROUTER_MODEL = "inclusionai/ling-3.0-flash:free"


def get_openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)


def call_openrouter_api(prompt: str, model: str | None = None) -> str:
    """Helper para chamadas OpenRouter API."""
    import requests
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    target_model = model or get_openrouter_model()
    if not api_key:
        return f"Mock LLM Response for model {target_model}"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": target_model,
        "messages": [{"role": "user", "content": prompt}],
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    return f"Fallback response for model {target_model}"


def compress_prompt(text: str, max_chars: int = 6000) -> str:
    """Compacta prompts removendo linhas em branco duplicadas e espaços desnecessários."""
    if not text:
        return ""
    compressed = re.sub(r"\n{3,}", "\n\n", text)
    compressed = "\n".join(re.sub(r"(?<=\S)[ \t]{2,}", " ", line) for line in compressed.splitlines())
    if len(compressed) > max_chars:
        half = max_chars // 2
        compressed = compressed[:half] + "\n\n[... PROMPT COMPRESSÃO SEMÂNTICA LOOPFORGE ...]\n\n" + compressed[-half:]
    return compressed.strip()


def _semantic_normalize_prompt(prompt: str) -> str:
    norm = prompt.lower()
    norm = re.sub(r"\b20\d{2}-\d{2}-\d{2}[tT ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:z|Z)?\b", "", norm)
    norm = re.sub(r"\s+", " ", norm)
    return norm.strip()


class SQLiteLLMCache:
    """Cache semântico de chamadas LLM com SQLite."""

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

    def get(self, prompt: str) -> str | None:
        sem_prompt = _semantic_normalize_prompt(prompt)
        h = hashlib.sha256(sem_prompt.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT response FROM cache WHERE prompt_hash = ?", (h,))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, prompt: str, response: str):
        sem_prompt = _semantic_normalize_prompt(prompt)
        h = hashlib.sha256(sem_prompt.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)", (h, response))


# --- LLM PROVIDER ABSTRACTION LAYER ---

class BaseLLMProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_OPENROUTER_MODEL,
        temperature: float = 0.2,
        schema_model: Optional[Type[BaseModel]] = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
    ) -> Any:
        pass


class OpenCodeCLIProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "opencode"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_OPENROUTER_MODEL,
        temperature: float = 0.2,
        schema_model: Optional[Type[BaseModel]] = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
    ) -> Any:
        from ..runner.opencode import call_llm_via_opencode
        return call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            schema_model=schema_model,
            mock=mock,
            cache=cache,
            circuit_breaker=circuit_breaker,
        )


class LLMProviderRegistry:
    """Registro desacoplado de provedores de LLM para orquestração heterogênea."""
    _providers: Dict[str, BaseLLMProvider] = {}
    _default_provider: str = "opencode"

    @classmethod
    def register(cls, provider: BaseLLMProvider) -> None:
        cls._providers[provider.provider_name.lower()] = provider

    @classmethod
    def get(cls, name: Optional[str] = None) -> BaseLLMProvider:
        target = (name or cls._default_provider).lower()
        return cls._providers.get(target, cls._providers.get("opencode", OpenCodeCLIProvider()))


LLMProviderRegistry.register(OpenCodeCLIProvider())
