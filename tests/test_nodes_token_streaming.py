"""Testes unitários para emissão de streaming de tokens (TokenDeltaPublisher) em nós do pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from lf.pipeline.llm_factory import TokenDeltaPublisher
from lf.runner.opencode.llm import call_llm_via_opencode


@pytest.mark.asyncio
async def test_token_delta_publisher_publish():
    published = []

    async def fake_publish(run_id, event, payload):
        published.append((run_id, event, payload))

    publisher = TokenDeltaPublisher("test-123", "cpo")
    with patch("lf.api.events.event_bus.publish", side_effect=fake_publish):
        await publisher._publish("Hello ")
        await publisher._publish("World")

    assert len(published) == 2
    assert published[0] == ("test-123", "token_delta", {"node": "cpo", "content": "Hello "})
    assert published[1] == ("test-123", "token_delta", {"node": "cpo", "content": "World"})


def test_call_llm_auto_creates_token_delta_publisher():
    captured_callback = None

    def fake_call_openrouter(prompt, **kwargs):
        nonlocal captured_callback
        captured_callback = kwargs.get("on_token_delta")
        if captured_callback:
            captured_callback("Token1 ")
            captured_callback("Token2")
        return "Complete response", {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}

    with (
        patch("os.environ.get", return_value="fake-api-key"),
        patch("lf.pipeline.llm_factory.call_openrouter_api", side_effect=fake_call_openrouter),
        patch.object(TokenDeltaPublisher, "__call__") as mock_call,
    ):
        result = call_llm_via_opencode(
            system_prompt="sys",
            user_prompt="user",
            mock=False,
            cache=False,
            node="tech_lead",
            run_id="run-456",
        )

        assert result == "Complete response"
        assert captured_callback is not None
        assert mock_call.call_count == 2
        mock_call.assert_any_call("Token1 ")
        mock_call.assert_any_call("Token2")
