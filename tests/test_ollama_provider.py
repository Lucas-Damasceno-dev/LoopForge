"""Testes do OllamaProvider: auto-descoberta de modelos (/api/tags) e stream de tokens."""
import pytest
from httpx import MockTransport, Response

from lf.pipeline.providers.ollama import OllamaProvider


def _tags_body() -> str:
    return '{"models": [{"name": "llama3.2"}, {"name": "qwen2.5"}]}'


def test_discover_models_parses_tags():
    provider = OllamaProvider(base_url="http://ollama:11434")

    def fake(request):
        assert request.url.path == "/api/tags"
        return Response(200, text=_tags_body(), request=request)

    provider._client = provider._client.__class__(transport=MockTransport(fake))
    assert provider.discover_models() == ["llama3.2", "qwen2.5"]


@pytest.mark.asyncio
async def test_ollama_stream_emits_tokens():
    provider = OllamaProvider(base_url="http://ollama:11434")

    def fake(request):
        assert request.url.path == "/api/chat"
        return Response(
            200,
            text='{"message":{"content":"a"}}\n{"message":{"content":"b"}}\n',
            request=request,
        )

    provider._async_client = provider._async_client.__class__(transport=MockTransport(fake))
    tokens = [t async for t in provider.stream([{"role": "user", "content": "hi"}], model="llama3.2")]
    assert tokens == ["a", "b"]
