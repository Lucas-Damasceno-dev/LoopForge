"""Testes do NativeLLMProvider: generate (SSE parse) e stream (deltas em ordem)."""
from contextlib import asynccontextmanager

import pytest
from httpx import Request, Response

from lf.pipeline.cache import SQLiteLLMCache
from lf.pipeline.llm_factory import LLMProviderRegistry, NativeLLMProvider


def _sse_body() -> str:
    return (
        'data: {"choices":[{"delta":{"content":"Ola"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":" mundo"}}]}\n\n'
        "data: [DONE]\n\n"
    )


@pytest.fixture
def native():
    return NativeLLMProvider(api_key="test-key")


def test_native_generate_parses_text(native, monkeypatch):
    # Garante determinismo: descarta cache residual de runs anteriores.
    SQLiteLLMCache().clear()
    captured = {}

    def fake_request(url, **kwargs):
        captured["json"] = kwargs.get("json") or {}
        return Response(200, text=_sse_body(), request=Request("POST", url))

    monkeypatch.setattr(native._client, "post", fake_request)
    text = native.generate("sys", "user", model="auto/best-free")
    assert text == "Ola mundo"
    assert captured["json"]["stream"] is False


@pytest.mark.asyncio
async def test_native_stream_emits_tokens_in_order(native, monkeypatch):
    @asynccontextmanager
    async def fake_stream(*args, **kwargs):
        yield Response(200, text=_sse_body(), request=Request("POST", "http://test"))

    monkeypatch.setattr(native._async_client, "stream", fake_stream)
    tokens = [tok async for tok in native.stream("sys", "user")]
    assert tokens == ["Ola", " mundo"]


def test_native_registered_in_registry():
    provider = LLMProviderRegistry.get("native")
    assert provider.provider_name == "native"
