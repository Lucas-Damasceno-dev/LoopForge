import asyncio
import contextlib
import json
import logging
import os
import re
import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cache import SQLiteLLMCache, _connect_sqlite, _semantic_normalize_prompt

logger = logging.getLogger(__name__)

__all__ = [
    "SQLiteLLMCache",
    "_semantic_normalize_prompt",
    "DEFAULT_LLM_MODEL",
    "resolve_default_model",
]

# Fonte única do modelo LLM default (Fix 2): os 5 defaults divergentes
# (runner.py, llm_factory.py, init.py, task_dispatcher.py e schema.py) agora
# convergem para esta constante canônica via resolve_default_model().
DEFAULT_LLM_MODEL = "oc/deepseek-v4-flash-free"


def resolve_default_model() -> str:
    """Resolve o modelo LLM default com precedência única (Fix 2).

    OPENROUTER_MODEL → OPENCODE_MODEL → config .loopforge.json (llm_model)
    → DEFAULT_LLM_MODEL (constante canônica — antes havia 5 defaults
    divergentes espalhados). Config resolve em call-time; falha silenciosa
    para a constante quando o arquivo de config está ausente/inválido.
    """
    env_model = os.getenv("OPENROUTER_MODEL") or os.getenv("OPENCODE_MODEL")
    if env_model:
        return env_model
    try:
        from lf.config.loader import load_config

        cfg = load_config()
        if cfg and getattr(cfg, "llm_model", None):
            return cfg.llm_model
    except Exception:
        pass
    return DEFAULT_LLM_MODEL


DEFAULT_OPENROUTER_MODEL = resolve_default_model()
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
                with (
                    httpx.Client(timeout=timeout_val) as client,
                    client.stream("POST", url, headers=headers, json=payload) as resp,
                ):
                    if resp.status_code != 200:
                        last_error = RuntimeError(
                            f"OpenRouter API request failed with status {resp.status_code}: {(resp.text or '')[:200]}"
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


# --- STREAMING TOKEN A TOKEN (V1.1/ADR-0007) ---


# O callback recebe chunks incrementais do provedor; `TokenDeltaPublisher` os
# publica como eventos `token_delta` no EventBus (envelope v1: {seq, event,
# run_id, timestamp, payload}). Não-invasivo por design: sem callback
# registrado, nenhum evento é emitido e o pipeline segue o fluxo atual;
# falhas de publicação são descartadas em silêncio (nunca derruba nem atrasa
# o pipeline).


class TokenDeltaPublisher:
    """Publica deltas de streaming como eventos ``token_delta`` serializados.

    Os nós síncronos do LangGraph rodam em thread do ThreadPoolExecutor (sem
    loop asyncio) — por isso o publisher mantém UMA thread daemon com loop
    asyncio próprio. ``__call__`` agenda o delta via ``call_soon_threadsafe``
    (não bloqueia o pipeline) e o drain serializado garante seq monotônico.
    Nunca levanta exceção — falha silenciosa por design.
    """

    def __init__(self, run_id: str, node: str) -> None:
        self.run_id = run_id
        self.node = node
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._queue: asyncio.Queue[str] | None = None

    def __call__(self, content: str) -> None:
        if not content:
            return
        if self._thread is None or not self._thread.is_alive():
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(target=self._run_loop, name="token-delta-publisher", daemon=True)
            self._thread.start()
        assert self._loop is not None
        self._loop.call_soon_threadsafe(self._enqueue, content)

    def _run_loop(self) -> None:
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        # Fila criada dentro do loop: acessada apenas via call_soon_threadsafe.
        self._queue = asyncio.Queue()
        self._loop.create_task(self._drain())
        self._loop.run_forever()

    def _enqueue(self, content: str) -> None:
        # Executa dentro do loop (agendado via call_soon_threadsafe).
        if self._queue is not None:
            self._queue.put_nowait(content)

    async def _drain(self) -> None:
        """Consome a fila na ordem de chegada, publicando cada delta no EventBus."""
        assert self._queue is not None
        while True:
            content = await self._queue.get()
            with contextlib.suppress(Exception):
                await self._publish(content)

    async def _publish(self, content: str) -> None:
        # Import tardio evita ciclo api↔pipeline (llm_factory não importa fastapi).
        from lf.api.events import event_bus

        await event_bus.publish(self.run_id, "token_delta", {"node": self.node, "content": content})
