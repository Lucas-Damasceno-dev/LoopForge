import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

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

    def get(self, prompt: str) -> str | None:
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
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL
)

FALLBACK_OPENROUTER_MODELS = [
    "inclusionai/ling-3.0-flash:free",
    "google/gemini-2.0-flash-lite:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
]


def _is_default_openrouter() -> bool:
    """Retorna True se estiver usando a URL padrão do OpenRouter."""
    url = os.environ.get("OPENROUTER_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
    return url.rstrip("/") == _DEFAULT_OPENROUTER_BASE_URL


def call_openrouter_api(
    prompt: str,
    model: str = DEFAULT_OPENROUTER_MODEL,
    temperature: float = 0.2,
    api_key: str | None = None,
    timeout: float = 60.0,
) -> str:
    """Realiza uma chamada à API do OpenRouter via httpx com cadeia automática de fallback de modelos."""
    import httpx

    key = api_key or os.environ.get("OPENROUTER_API_KEY") or DEFAULT_OPENROUTER_KEY
    if not key:
        raise ValueError("OPENROUTER_API_KEY não foi configurada.")

    base_url = os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_OPENROUTER_BASE_URL
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://loopforge.dev",
        "X-Title": "LoopForge AI Engine",
    }

    models_to_try = (
        [model] + [m for m in FALLBACK_OPENROUTER_MODELS if m != model]
        if _is_default_openrouter()
        else [model]
    )
    last_exception = None

    for m in models_to_try:
        payload = {
            "model": m,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "stream": False,
        }

        try:
            response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if choices and choices[0].get("message", {}).get("content"):
                    return choices[0]["message"]["content"]
            elif response.status_code in (429, 404) or "rate-limited" in response.text or "Model not found" in response.text:
                tag = "OpenRouter" if _is_default_openrouter() else "LLM API"
                print(f"--- AVISO: {tag} modelo '{m}' indisponível ({response.status_code}). Tentando fallback... ---")
                last_exception = RuntimeError(f"{tag} error ({response.status_code}): {response.text}")
                continue
            else:
                last_exception = RuntimeError(f"LLM API error ({response.status_code}): {response.text}")
        except Exception as e:
            last_exception = e
            continue

    if last_exception:
        raise last_exception
    raise RuntimeError("LLM API falhou em todos os modelos da cadeia de fallback.")


def get_llm(provider: str = "openrouter", model_name: str = DEFAULT_OPENROUTER_MODEL, temperature: float = 0.2) -> Any:
    """Retorna instância de LLM ou função de fallback baseada nas variáveis de ambiente."""
    api_key = os.environ.get("OPENROUTER_API_KEY") or DEFAULT_OPENROUTER_KEY
    if provider == "openrouter" or api_key:
        return lambda prompt: call_openrouter_api(prompt, model=model_name, temperature=temperature, api_key=api_key)

    api_key_gemini = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key_gemini:
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
