"""Testes do streaming token a token (V1.1/ADR-0007) — eventos ``token_delta``.

Cobre: (1) publicação via EventBus com envelope v1; (2) streaming incremental
em ``call_openrouter_api``; (3) serialização do TokenDeltaPublisher; (4) repasse
do callback por ``call_llm_via_opencode``.
"""

import asyncio
from uuid import uuid4

import pytest

from lf.pipeline.llm_factory import TokenDeltaPublisher, call_openrouter_api

SSE_LINES = [
    'data: {"choices":[{"delta":{"content":"Ola"}}]}',
    'data: {"choices":[{"delta":{"content":" "}}]}',
    'data: {"choices":[{"delta":{"content":"mundo"}}]}',
    "data: [DONE]",
    "",
]


@pytest.mark.asyncio
async def test_event_bus_token_delta_envelope_v1():
    """Envelope v1 do evento token_delta via event_bus.publish (seq 1)."""
    from lf.api.events import event_bus

    run_id = f"run-test-{uuid4().hex[:8]}"
    envelope = await event_bus.publish(run_id, "token_delta", {"node": "developer", "content": "Ola"})

    assert envelope["event"] == "token_delta"
    assert envelope["run_id"] == run_id
    assert envelope["seq"] == 1
    assert envelope["payload"] == {"node": "developer", "content": "Ola"}
    assert envelope["timestamp"]


def test_call_openrouter_api_streams_deltas_via_callback(monkeypatch):
    """Com on_token_delta, a chamada usa SSE streaming e repassa cada chunk."""
    import httpx

    class FakeResp:
        status_code = 200

        def iter_lines(self):
            yield from SSE_LINES

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url, headers=None, json=None):
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    deltas: list[str] = []
    text, _usage = call_openrouter_api("prompt", max_retries=0, on_token_delta=deltas.append)

    assert text == "Ola mundo"
    assert deltas == ["Ola", " ", "mundo"]


@pytest.mark.asyncio
async def test_token_delta_publisher_serializa_publicacoes(monkeypatch):
    """TokenDeltaPublisher publica em ordem via thread daemon própria."""
    from lf.api import events as events_mod

    captured: list[tuple[str, str, dict]] = []

    async def fake_publish(run_id, event_type, payload):
        captured.append((run_id, event_type, payload))

    monkeypatch.setattr(events_mod.event_bus, "publish", fake_publish)

    pub = TokenDeltaPublisher("run-abc-123", "developer")
    pub("Ola")
    pub(" ")
    pub("mundo")

    for _ in range(300):
        if len(captured) == 3:
            break
        await asyncio.sleep(0.01)

    assert [c[1] for c in captured] == ["token_delta", "token_delta", "token_delta"]
    assert [c[2]["content"] for c in captured] == ["Ola", " ", "mundo"]
    assert all(c[2]["node"] == "developer" for c in captured)
    assert all(c[0] == "run-abc-123" for c in captured)


def test_call_llm_via_opencode_repassa_on_token_delta(monkeypatch):
    """call_llm_via_opencode repassa o callback ao call_openrouter_api."""
    import lf.pipeline.llm_factory as llm_factory
    from lf.runner.opencode import llm as llm_mod

    captured: dict = {}

    def fake_call_openrouter_api(
        prompt, model=None, api_key=None, base_url=None, system_prompt=None, max_retries=2, on_token_delta=None
    ):
        captured["cb"] = on_token_delta
        return ("resposta", {"prompt_tokens": 1, "completion_tokens": 1})

    monkeypatch.setattr(llm_factory, "call_openrouter_api", fake_call_openrouter_api)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    cb = lambda s: None  # noqa: E731
    out = llm_mod.call_llm_via_opencode("sys", "user-unique-forward", on_token_delta=cb)

    assert captured["cb"] is cb
    assert out == "resposta"
