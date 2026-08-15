"""Rate limiting (sliding window) para a API do LoopForge.

Sem dependência externa no caminho default: janela deslizante por chave — IP do
cliente ou header ``X-API-Key`` quando presente. O estado é por-processo
(aceitável para a API local/single-worker). Com ``redis`` configurado
(multi-worker, backend=redis), a janela é GLOBAL via ZSET ``lf:rl:{key}``.
WebSockets e ``/health`` não são limitados; requisições OPTIONS (preflight
CORS) também passam ilesas.
"""

import time

from starlette.responses import JSONResponse


class RateLimitMiddleware:
    """Middleware ASGI puro: responde 429 + Retry-After quando a janela estourar.

    Implementado como ASGI puro (não BaseHTTPMiddleware) para não interferir em
    streaming/background tasks e passar por WebSockets sem custo (scope type
    ``websocket`` é ignorado).
    """

    def __init__(self, app, limit_per_min: int = 300, window_seconds: int = 60, redis=None) -> None:
        self.app = app
        self.limit = limit_per_min
        self.window = window_seconds
        self.redis = redis  # Redis | None — None = in-memory (BC)
        # key -> timestamps (time.monotonic) das requests dentro da janela
        self._hits: dict[str, list[float]] = {}
        self._prune_threshold = 10_000

    def _client_key(self, scope: dict) -> str:
        """Chave por X-API-Key (quando presente) ou IP do cliente."""
        headers = dict(scope.get("headers") or [])
        api_key = headers.get(b"x-api-key")
        if api_key:
            return f"key:{api_key.decode(errors='ignore')}"
        client = scope.get("client") or ("unknown", 0)
        return f"ip:{client[0]}"

    async def _check_window(self, key: str, now: float) -> tuple[bool, int]:
        """Janela deslizante: remove entradas expiradas e conta as restantes.

        Retorna (permitido, retry_after_seconds) — retry_after > 0 apenas
        quando a janela estourou (tempo até a request mais antiga expirar).
        Com redis: ZSET ``lf:rl:{key}`` (score = timestamp), operações em
        pipeline único (prune + count + insert + TTL).
        """
        if self.redis is not None:
            rkey = f"lf:rl:{key}"
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(rkey, "-inf", now - self.window)
            pipe.zcard(rkey)
            pipe.zadd(rkey, {str(now): now})
            pipe.expire(rkey, self.window * 2)
            _, count, _, _ = await pipe.execute()
            if int(count) >= self.limit:
                return False, 1
            return True, 0
        cutoff = now - self.window
        window = self._hits.setdefault(key, [])
        while window and window[0] <= cutoff:
            window.pop(0)
        if len(window) >= self.limit:
            retry_after = max(1, int(window[0] + self.window - now) + 1)
            return False, retry_after
        window.append(now)
        return True, 0

    def _prune_stale(self) -> None:
        """Remove chaves sem requests ativas quando o mapa crescer demais."""
        if len(self._hits) <= self._prune_threshold:
            return
        cutoff = time.monotonic() - self.window
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in stale:
            del self._hits[key]

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or self.limit <= 0:
            await self.app(scope, receive, send)
            return
        # /health e OPTIONS (preflight CORS) passam sem contabilizar.
        if scope.get("path") == "/health" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        now = time.monotonic()
        key = self._client_key(scope)
        allowed, retry_after = await self._check_window(key, now)
        if not allowed:
            response = JSONResponse(
                {"detail": "Rate limit excedido. Tente novamente em instantes."},
                status_code=429,
            )
            response.headers["Retry-After"] = str(retry_after)
            response.headers["X-RateLimit-Limit"] = str(self.limit)
            await response(scope, receive, send)
            return

        self._prune_stale()
        await self.app(scope, receive, send)
