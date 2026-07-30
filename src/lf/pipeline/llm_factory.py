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
DEFAULT_OPENROUTER_KEY = ""
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)


def call_openrouter_api(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    api_key: str | None = None,
    base_url: str = _DEFAULT_OPENROUTER_BASE_URL,
) -> str:
    """Helper para chamadas OpenRouter API via httpx."""
    import httpx
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "") or DEFAULT_OPENROUTER_KEY
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
    }

    resp = httpx.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    raise RuntimeError(f"OpenRouter API request failed with status {resp.status_code}: {resp.text}")


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


class CostTracker:
    """Rastreamento de tokens e cálculo de custo estimado em USD por chamada LLM."""

    PRICING_PER_1K_TOKENS = {
        "inclusionai/ling-3.0-flash:free": (0.0, 0.0),
        "anthropic/claude-3.5-sonnet": (0.003, 0.015),
        "openai/gpt-4o-mini": (0.00015, 0.0006),
        "default": (0.001, 0.002),
    }

    def __init__(self, db_path: str | Path = ".loopforge/telemetry.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def track(self, model: str, prompt_text: str, response_text: str) -> float:
        prompt_tokens = max(1, len(prompt_text) // 4)
        completion_tokens = max(1, len(response_text) // 4)

        rates = self.PRICING_PER_1K_TOKENS.get(model, self.PRICING_PER_1K_TOKENS["default"])
        cost = ((prompt_tokens / 1000.0) * rates[0]) + ((completion_tokens / 1000.0) * rates[1])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd) VALUES (?, ?, ?, ?)",
                (model, prompt_tokens, completion_tokens, cost),
            )
        return cost


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


class OpenRouterProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "openrouter"

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
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        if mock:
            return f"[MOCK OpenRouter] Response for: {user_prompt[:50]}"
        text = call_openrouter_api(full_prompt, model=model)
        CostTracker().track(model, full_prompt, text)
        if schema_model:
            try:
                return json.loads(text)
            except Exception:
                pass
        return text


class MockLLMProvider(BaseLLMProvider):
    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "mock",
        temperature: float = 0.0,
        schema_model: Optional[Type[BaseModel]] = None,
        mock: bool = True,
        cache: bool = False,
        circuit_breaker: Any = None,
    ) -> Any:
        mock_text = f"[MOCK Provider] Resposta para: {user_prompt[:80]}"
        if schema_model:
            return schema_model.model_construct()
        return mock_text


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
LLMProviderRegistry.register(OpenRouterProvider())
LLMProviderRegistry.register(MockLLMProvider())


def execute_llm(
    system_prompt: str,
    user_prompt: str,
    provider_name: str | None = None,
    model: str = DEFAULT_OPENROUTER_MODEL,
    schema_model: Optional[Type[BaseModel]] = None,
    mock: bool = False,
    cache: bool = True,
    circuit_breaker: Any = None,
) -> Any:
    """Ponto de entrada unificado que consome o LLMProviderRegistry."""
    target_provider = LLMProviderRegistry.get(provider_name)
    return target_provider.generate(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model=model,
        schema_model=schema_model,
        mock=mock,
        cache=cache,
        circuit_breaker=circuit_breaker,
    )
