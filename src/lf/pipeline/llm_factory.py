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
) -> tuple[str, dict | None]:
    """Helper para chamadas OpenRouter API via httpx.

    Returns (text, usage_dict) onde usage_dict contém prompt_tokens e completion_tokens
    retornados pela API, ou None se indisponível.
    """
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
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage")
        return text, usage

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

def _connect_sqlite(db_path: str | Path) -> sqlite3.Connection:
    """Abre conexão SQLite com WAL mode e busy_timeout ativados."""
    conn = sqlite3.connect(db_path, timeout=10.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
    except Exception:
        pass
    return conn


class SQLiteLLMCache:
    """Cache semântico de chamadas LLM com SQLite."""

    def __init__(self, db_path: str | Path = ".loopforge/llm_cache.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with _connect_sqlite(self.db_path) as conn:
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
        with _connect_sqlite(self.db_path) as conn:
            cur = conn.execute("SELECT response FROM cache WHERE prompt_hash = ?", (h,))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, prompt: str, response: str):
        sem_prompt = _semantic_normalize_prompt(prompt)
        h = hashlib.sha256(sem_prompt.encode()).hexdigest()
        with _connect_sqlite(self.db_path) as conn:
            conn.execute("INSERT OR REPLACE INTO cache (prompt_hash, response) VALUES (?, ?)", (h, response))


class CostTracker:
    """Rastreamento de tokens e cálculo de custo estimado em USD por chamada LLM.

    Usa tiktoken (se disponível) para contagem precisa de tokens.
    Aceita token counts reais da API (usage) como fonte primária.
    Fallback: estimativa chars//4.
    """

    PRICING_PER_1K_TOKENS = {
        "inclusionai/ling-3.0-flash:free": (0.0, 0.0),
        "anthropic/claude-3.5-sonnet": (0.003, 0.015),
        "anthropic/claude-3-opus": (0.015, 0.075),
        "anthropic/claude-3-haiku": (0.00025, 0.00125),
        "openai/gpt-4o": (0.0025, 0.01),
        "openai/gpt-4o-mini": (0.00015, 0.0006),
        "openai/gpt-4-turbo": (0.01, 0.03),
        "openai/gpt-3.5-turbo": (0.001, 0.002),
        "google/gemini-1.5-flash": (0.000075, 0.0003),
        "google/gemini-1.5-pro": (0.00125, 0.005),
        "meta-llama/llama-3-70b": (0.0008, 0.001),
        "mistral/mistral-large": (0.002, 0.006),
        "default": (0.001, 0.002),
    }

    # Cache singleton do encoding tiktoken por modelo
    _encodings: dict[str, Any] = {}

    def __init__(self, db_path: str | Path = ".loopforge/telemetry.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with _connect_sqlite(self.db_path) as conn:
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

    @staticmethod
    def _count_tokens(text: str, model: str = "") -> int:
        """Conta tokens usando tiktoken (se disponível) ou fallback chars//4."""
        try:
            import tiktoken
            # Mapeamento aproximado de modelo → encoding
            enc_name = "cl100k_base"  # default para GPT-4, GPT-3.5
            if "gpt-4" in model or "gpt-3.5" in model:
                enc_name = "cl100k_base"
            elif "gpt-4o" in model:
                enc_name = "o200k_base"
            elif "llama" in model or "mistral" in model:
                enc_name = "cl100k_base"
            encoding = tiktoken.get_encoding(enc_name)
            return len(encoding.encode(text))
        except ImportError:
            pass
        except Exception:
            pass
        # Fallback: ~4 chars por token (padrão OpenAI)
        return max(1, len(text) // 4)

    def track(
        self,
        model: str,
        prompt_text: str,
        response_text: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> float:
        if prompt_tokens is None:
            prompt_tokens = self._count_tokens(prompt_text, model)
        if completion_tokens is None:
            completion_tokens = self._count_tokens(response_text, model)

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
        text, usage = call_openrouter_api(full_prompt, model=model)
        # Passa token counts reais da API se disponíveis
        pt = usage.get("prompt_tokens") if usage else None
        ct = usage.get("completion_tokens") if usage else None
        CostTracker().track(model, full_prompt, text, prompt_tokens=pt, completion_tokens=ct)
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
