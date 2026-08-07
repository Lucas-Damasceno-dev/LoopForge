"""Provider Ollama (LLMs locais) com auto-descoberta via /api/tags."""
import json
import os
from collections.abc import AsyncIterator

import httpx


class OllamaProvider:
    provider_name = "ollama"

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")
        self._client = httpx.Client(timeout=60.0)
        self._async_client = httpx.AsyncClient(timeout=60.0)

    def discover_models(self) -> list[str]:
        resp = self._client.get(f"{self.base_url}/api/tags")
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]

    def chat(self, messages: list[dict], model: str, stream: bool = False) -> str:
        resp = self._client.post(
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": stream},
        )
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    async def stream(self, messages: list[dict], model: str) -> AsyncIterator[str]:
        async with self._async_client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={"model": model, "messages": messages, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    content = json.loads(line).get("message", {}).get("content", "")
                except json.JSONDecodeError:
                    content = ""
                if content:
                    yield content
