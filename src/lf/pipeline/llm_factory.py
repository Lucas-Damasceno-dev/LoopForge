import asyncio
import contextlib
import json
import os
import queue
import re
import sqlite3
import threading
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from lf.pipeline.providers.ollama import OllamaProvider

from .cache import SQLiteLLMCache, _connect_sqlite, _semantic_normalize_prompt

__all__ = ["SQLiteLLMCache", "_semantic_normalize_prompt"]

DEFAULT_OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "auto/best-free")
DEFAULT_OPENROUTER_KEY = ""
_DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Default elevado para chamadas HTTP ao LLM: o antigo 60s fixo (P2-5) cortava
# modelos de reasoning (deepseek-r1, o1/o3, etc.), que pensam por minutos.
# Override via env OPENROUTER_TIMEOUT. Nunca usar timeout None/infinito.
DEFAULT_LLM_TIMEOUT = 300.0
# Margem extra para modelos de reasoning (raciocínio longo em prompts grandes).
REASONING_TIMEOUT = 600.0
# Marcadores de nome de modelo de reasoning no OpenRouter (lowercase): ex.
# deepseek-r1, openai o1/o3, kimi-k2, z-ai/glm-4.5, claude-3-7-sonnet (thinking).
_REASONING_MODEL_MARKERS = frozenset(
    {"reasoner", "reasoning", "thinking", "r1", "o1", "o3", "deepseek-r", "kimi", "glm-4.5"}
)


def _is_reasoning_model(model: str) -> bool:
    """Detecta modelo de reasoning pelo nome (lowercase), ex.: deepseek-r1, o3-mini."""
    lowered = model.lower()
    return any(marker in lowered for marker in _REASONING_MODEL_MARKERS)


def _resolve_timeout(model: str, env_timeout: str | None) -> float:
    """Resolve o timeout de chamada LLM: env > reasoning > default (nunca None/infinito)."""
    if env_timeout:
        try:
            parsed = float(env_timeout)
            if parsed > 0:
                return parsed
        except ValueError:
            pass
    if _is_reasoning_model(model):
        return REASONING_TIMEOUT
    return DEFAULT_LLM_TIMEOUT


def get_openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)


def call_openrouter_api(
    prompt: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
    max_retries: int = 2,
    on_token_delta: Callable[[str], None] | None = None,
) -> tuple[str, dict | None]:
    """Helper para chamadas OpenRouter API via httpx com retentativas automáticas e backoff.

    Quando ``on_token_delta`` é fornecido, a chamada usa streaming (SSE) e cada
    chunk incremental é repassado ao callback — sem custo extra de latência,
    pois o texto final é consolidado a partir dos próprios chunks.
    """
    import time

    import httpx

    target_model = model or os.environ.get("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL
    key = api_key or os.environ.get("OPENROUTER_API_KEY", "") or DEFAULT_OPENROUTER_KEY
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    effective_base_url = base_url or os.environ.get("OPENROUTER_BASE_URL", _DEFAULT_OPENROUTER_BASE_URL)
    url = f"{effective_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    streaming = on_token_delta is not None
    payload = {
        "model": target_model,
        "messages": messages,
        "stream": streaming,
    }

    # Timeout configurável via OPENROUTER_TIMEOUT (segundos). Sem a env, usa o
    # default elevado (DEFAULT_LLM_TIMEOUT / REASONING_TIMEOUT p/ reasoning) —
    # nunca sem timeout (P2-5).
    base_timeout = _resolve_timeout(target_model, os.environ.get("OPENROUTER_TIMEOUT"))
    last_error: Exception | None = None
    empty_content = False

    for attempt in range(max_retries + 1):
        try:
            timeout_val = base_timeout * (1.0 + attempt * 0.5)
            if streaming:
                assert on_token_delta is not None
                chunks: list[str] = []
                usage = None
                with httpx.Client(timeout=timeout_val) as client:
                    with client.stream("POST", url, headers=headers, json=payload) as resp:
                        if resp.status_code != 200:
                            last_error = RuntimeError(
                                f"OpenRouter API request failed with status {resp.status_code}: "
                                f"{(resp.text or '')[:200]}"
                            )
                            continue
                        for line in resp.iter_lines():
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            data_line = line[6:]
                            if data_line == "[DONE]":
                                break
                            try:
                                cdata = json.loads(data_line)
                            except Exception:
                                continue
                            choices = cdata.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content") or choices[0].get("message", {}).get("content")
                                if content:
                                    chunks.append(content)
                                    on_token_delta(content)
                            if cdata.get("usage"):
                                usage = cdata["usage"]
                text = "".join(chunks)
                if not text:
                    empty_content = True
                    raise RuntimeError("OpenRouter API retornou content vazio (streaming)")
                return text, usage
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout_val)
            if resp.status_code == 200:
                raw_text = resp.text if hasattr(resp, "text") and isinstance(resp.text, str) else ""
                raw_text = raw_text.strip()
                if raw_text.startswith("data:") or "\ndata: {" in raw_text:
                    chunks = []
                    usage = None
                    for line in raw_text.splitlines():
                        line = line.strip()
                        if line.startswith("data: ") and line != "data: [DONE]":
                            try:
                                cdata = json.loads(line[6:])
                                choices = cdata.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content") or choices[0].get("message", {}).get("content")
                                    if content:
                                        chunks.append(content)
                                if cdata.get("usage"):
                                    usage = cdata["usage"]
                            except Exception:
                                pass
                    text = "".join(chunks)
                    if not text:
                        empty_content = True
                        raise RuntimeError("OpenRouter API retornou content vazio (streaming)")
                    return text, usage
                else:
                    data = resp.json()
                    choice = data["choices"][0]
                    msg = choice.get("message", {})
                    text = msg.get("content") or choice.get("delta", {}).get("content", "")
                    usage = data.get("usage")
                    if not text:
                        empty_content = True
                        raise RuntimeError("OpenRouter API retornou content vazio")
                    return text, usage
            else:
                last_error = RuntimeError(
                    f"OpenRouter API request failed with status {resp.status_code}: {resp.text[:200]}"
                )
        except Exception as err:
            last_error = err
            if attempt < max_retries:
                print(
                    f"--- AVISO: Chamada LLM API (tentativa {attempt + 1}/{max_retries + 1}) falhou ({err}). Retentando em {(attempt + 1) * 2}s... ---"
                )
                time.sleep((attempt + 1) * 2)

    # Esgotou as retentativas: se o motivo foi content vazio, retorna '' (não
    # lança exceção prematura); caso contrário propaga o último erro real.
    if empty_content:
        return "", None
    raise last_error or RuntimeError("OpenRouter API request failed after retries")


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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    run_id TEXT,
                    node TEXT,
                    estimated INTEGER DEFAULT 0
                )
                """
            )
            self._apply_additive_migration(conn)

    @staticmethod
    def _apply_additive_migration(conn) -> None:
        """Migração aditiva de ``llm_costs`` (M-08/M-09).

        Adiciona ``run_id``, ``node`` e ``estimated`` quando ausentes (detecção
        via PRAGMA table_info + ALTER TABLE) — mesma técnica idempotente de
        ``_apply_pipeline_runs_additive_migration`` em lf/api/database.py, mas
        SEM tocar naquele módulo (outro lane). Rodar N vezes é seguro; em DBs
        com schema novo (CREATE acima já com as colunas) é read-only.
        """
        try:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(llm_costs)")}
            if "run_id" not in columns:
                conn.execute("ALTER TABLE llm_costs ADD COLUMN run_id TEXT")
            if "node" not in columns:
                conn.execute("ALTER TABLE llm_costs ADD COLUMN node TEXT")
            if "estimated" not in columns:
                conn.execute("ALTER TABLE llm_costs ADD COLUMN estimated INTEGER DEFAULT 0")
        except Exception as exc:
            # Tabela recém-criada ou sem permissão: o CREATE já cobre o schema
            # novo; não deve quebrar o rastreamento por causa da migração.
            logger.warning("Migração aditiva de llm_costs não aplicada: %s", exc)

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
        run_id: str | None = None,
        node: str | None = None,
        estimated: bool = False,
    ) -> float:
        if prompt_tokens is None:
            prompt_tokens = self._count_tokens(prompt_text, model)
        if completion_tokens is None:
            completion_tokens = self._count_tokens(response_text, model)

        rates = self.PRICING_PER_1K_TOKENS.get(model, self.PRICING_PER_1K_TOKENS["default"])
        cost = ((prompt_tokens / 1000.0) * rates[0]) + ((completion_tokens / 1000.0) * rates[1])

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd, run_id, node, estimated) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (model, prompt_tokens, completion_tokens, cost, run_id, node, 1 if estimated else 0),
            )
        return cost


# --- LLM PROVIDER ABSTRACTION LAYER ---


# V1.1/ADR-0007 — streaming token a token. `TokenDeltaCallback` recebe chunks
# incrementais do provedor; `TokenDeltaPublisher` os publica como eventos
# `token_delta` no EventBus (envelope v1: {seq, event, run_id, timestamp,
# payload}). Não-invasivo por design: sem callback registrado, nenhum evento é
# emitido e o pipeline segue o fluxo atual; falhas de publicação são
# descartadas em silêncio (nunca derruba nem atrasa o pipeline).
TokenDeltaCallback = Callable[[str], None]


class TokenDeltaPublisher:
    """Publica deltas de streaming como eventos ``token_delta`` serializados.

    Os nós síncronos do LangGraph rodam em thread do ThreadPoolExecutor (sem
    loop asyncio) — por isso o publisher mantém UMA thread daemon com loop
    asyncio próprio e consome uma queue thread-safe. ``__call__`` apenas
    enfileira (put_nowait, não bloqueia o pipeline) e o drain serializado
    garante seq monotônico por run. Nunca levanta exceção — falha silenciosa
    por design.
    """

    def __init__(self, run_id: str, node: str) -> None:
        self.run_id = run_id
        self.node = node
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def __call__(self, content: str) -> None:
        if not content:
            return
        self._queue.put_nowait(content)
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_loop, name="token-delta-publisher", daemon=True)
            self._thread.start()

    def _run_loop(self) -> None:
        asyncio.run(self._drain())

    async def _drain(self) -> None:
        """Consome a queue na ordem de chegada, publicando cada delta no EventBus."""
        loop = asyncio.get_running_loop()
        while True:
            content = await loop.run_in_executor(None, self._queue.get)
            try:
                await self._publish(content)
            except Exception:
                pass

    async def _publish(self, content: str) -> None:
        # Import tardio evita ciclo api↔pipeline (llm_factory não importa fastapi).
        from lf.api.events import event_bus

        await event_bus.publish(self.run_id, "token_delta", {"node": self.node, "content": content})


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
        schema_model: type[BaseModel] | None = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
        on_token_delta: TokenDeltaCallback | None = None,
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
        schema_model: type[BaseModel] | None = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
        on_token_delta: TokenDeltaCallback | None = None,
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
            on_token_delta=on_token_delta,
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
        schema_model: type[BaseModel] | None = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
        on_token_delta: TokenDeltaCallback | None = None,
    ) -> Any:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        if mock:
            return f"[MOCK OpenRouter] Response for: {user_prompt[:50]}"
        text, usage = call_openrouter_api(full_prompt, model=model, on_token_delta=on_token_delta)
        # Passa token counts reais da API se disponíveis
        pt = usage.get("prompt_tokens") if usage else None
        ct = usage.get("completion_tokens") if usage else None
        # M-08/M-09: run_id/node não estão disponíveis neste caller (o estado
        # do pipeline não carrega run_id; o plumbing run_id→nó é feito no
        # dispatcher/app em outra lane). Ficam None — o custo ainda entra no
        # ledger agregado de llm_costs, sem dimensão de run.
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
        schema_model: type[BaseModel] | None = None,
        mock: bool = True,
        cache: bool = False,
        circuit_breaker: Any = None,
        on_token_delta: TokenDeltaCallback | None = None,
    ) -> Any:
        # Mock não gera streaming real — sem deltas sintéticos (V1.1/ADR-0007).
        mock_text = f"[MOCK Provider] Resposta para: {user_prompt[:80]}"
        if schema_model:
            return schema_model.model_construct()
        return mock_text


class NativeLLMProvider(BaseLLMProvider):
    """Provider LLM nativo via HTTP (OpenRouter/Zen), streaming token a token.

    Cadeia de fallback: nativo -> OpenCode CLI -> Mock. O cache SQLiteLLMCache
    guarda apenas o payload final consolidado; deltas intermediários nunca são
    persistidos (requisito de streaming).
    """

    @property
    def provider_name(self) -> str:
        return "native"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, timeout: float | None = None):
        import httpx

        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.base_url = base_url or _DEFAULT_OPENROUTER_BASE_URL
        # Default fixo de 60s cortava modelos de reasoning (P2-5): agora o
        # default é 300s (ou 600s se o modelo configurado for reasoning),
        # override via env OPENROUTER_TIMEOUT.
        self.timeout = (
            timeout
            if timeout is not None
            else _resolve_timeout(DEFAULT_OPENROUTER_MODEL, os.environ.get("OPENROUTER_TIMEOUT"))
        )
        self._client = httpx.Client(timeout=self.timeout)
        self._async_client = httpx.AsyncClient(timeout=self.timeout)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _parse_sse(self, body: str) -> str:
        text = []
        for line in body.splitlines():
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload).get("choices", [{}])[0].get("delta", {}).get("content", "")
            except Exception:
                delta = ""
            text.append(delta)
        return "".join(text)

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_OPENROUTER_MODEL,
        temperature: float = 0.2,
        schema_model: type[BaseModel] | None = None,
        mock: bool = False,
        cache: bool = True,
        circuit_breaker: Any = None,
    ) -> Any:
        from lf.pipeline.cache import SQLiteLLMCache

        if mock:
            return MockLLMProvider().generate(
                system_prompt, user_prompt, model=model, schema_model=schema_model, mock=True
            )
        if circuit_breaker is not None and not circuit_breaker.can_proceed():
            return self._fallback_generate(
                system_prompt, user_prompt, model, schema_model, mock, cache, circuit_breaker
            )
        full_prompt = f"{system_prompt}\n{user_prompt}"
        llm_cache = SQLiteLLMCache()
        if cache:
            hit = llm_cache.get(full_prompt)
            if hit is not None:
                return hit
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "stream": False,
        }
        try:
            resp = self._client.post(f"{self.base_url}/chat/completions", json=payload, headers=self._headers())
            resp.raise_for_status()
            text = self._parse_sse(resp.text)
        except Exception:
            return self._fallback_generate(
                system_prompt, user_prompt, model, schema_model, mock, cache, circuit_breaker
            )
        # Payload final consolidado -> cache (requisito: nunca deltas)
        if cache:
            llm_cache.set(full_prompt, text)
        # M-08/M-09: run_id/node indisponíveis neste caller (ver comentário em
        # OpenRouterProvider.generate) — ficam None, custo real sem dimensão
        # de run até o plumbing run_id→nó (outra lane).
        with contextlib.suppress(Exception):
            CostTracker().track(model, full_prompt, text)
        return text

    def _fallback_generate(self, system_prompt, user_prompt, model, schema_model, mock, cache, circuit_breaker):
        try:
            return OpenCodeCLIProvider().generate(
                system_prompt,
                user_prompt,
                model=model,
                schema_model=schema_model,
                mock=mock,
                cache=cache,
                circuit_breaker=circuit_breaker,
            )
        except Exception:
            return MockLLMProvider().generate(
                system_prompt, user_prompt, model=model, schema_model=schema_model, mock=True
            )

    async def stream(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = DEFAULT_OPENROUTER_MODEL,
        temperature: float = 0.2,
        circuit_breaker: Any = None,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "temperature": temperature,
            "stream": True,
        }
        async with self._async_client.stream(
            "POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    delta = json.loads(chunk).get("choices", [{}])[0].get("delta", {}).get("content", "")
                except Exception:
                    delta = ""
                if delta:
                    yield delta


class LLMProviderRegistry:
    """Registro desacoplado de provedores de LLM para orquestração heterogênea."""

    _providers: dict[str, BaseLLMProvider] = {}
    _default_provider: str = "opencode"

    @classmethod
    def register(cls, provider: BaseLLMProvider) -> None:
        cls._providers[provider.provider_name.lower()] = provider

    @classmethod
    def get(cls, name: str | None = None) -> BaseLLMProvider:
        target = (name or cls._default_provider).lower()
        return cls._providers.get(target, cls._providers.get("opencode", OpenCodeCLIProvider()))


LLMProviderRegistry.register(OpenCodeCLIProvider())
LLMProviderRegistry.register(OpenRouterProvider())
LLMProviderRegistry.register(MockLLMProvider())
LLMProviderRegistry.register(NativeLLMProvider())
LLMProviderRegistry.register(OllamaProvider())


def execute_llm(
    system_prompt: str,
    user_prompt: str,
    provider_name: str | None = None,
    model: str = DEFAULT_OPENROUTER_MODEL,
    schema_model: type[BaseModel] | None = None,
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
