"""P2-5: timeout default elevado para chamadas LLM (300s; 600s p/ modelos de reasoning).

Cobre os helpers `_is_reasoning_model`/`_resolve_timeout`, o uso em
`call_openrouter_api` e o default do `NativeLLMProvider` (antigo 60s fixo que
cortava reasoning models).
"""

import os
from unittest import mock

from httpx import Request, Response

from lf.pipeline.llm_factory import (
    DEFAULT_LLM_TIMEOUT,
    REASONING_TIMEOUT,
    NativeLLMProvider,
    _is_reasoning_model,
    _resolve_timeout,
    call_openrouter_api,
)


def test_is_reasoning_model_detecta_nomes_de_reasoning():
    assert _is_reasoning_model("deepseek/deepseek-r1") is True
    assert _is_reasoning_model("openai/o3-mini") is True
    assert _is_reasoning_model("openai/gpt-4o") is False
    assert _is_reasoning_model("openrouter/auto") is False


def test_resolve_timeout_prioriza_env_sobre_modelo():
    assert _resolve_timeout("openai/gpt-4o", "120") == 120.0
    assert _resolve_timeout("deepseek/deepseek-r1", "120") == 120.0


def test_resolve_timeout_reasoning_quando_sem_env():
    assert _resolve_timeout("deepseek/deepseek-r1", None) == REASONING_TIMEOUT
    assert _resolve_timeout("deepseek/deepseek-r1", "") == REASONING_TIMEOUT


def test_resolve_timeout_default_para_modelo_normal():
    assert _resolve_timeout("openai/gpt-4o", None) == DEFAULT_LLM_TIMEOUT


def test_resolve_timeout_env_invalida_cai_no_default():
    assert _resolve_timeout("openai/gpt-4o", "abc") == DEFAULT_LLM_TIMEOUT


def _fake_response() -> Response:
    return Response(200, json={"choices": [{"message": {"content": "ok"}}]}, request=Request("POST", "http://test"))


@mock.patch("httpx.post")
def test_call_openrouter_api_usa_timeout_default_para_modelo_normal(mock_post):
    mock_post.return_value = _fake_response()
    with mock.patch.dict(
        os.environ, {"OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL": "gpt-4o", "OPENROUTER_TIMEOUT": ""}
    ):
        call_openrouter_api(prompt="oi")
    assert mock_post.call_args.kwargs["timeout"] == DEFAULT_LLM_TIMEOUT


@mock.patch("httpx.post")
def test_call_openrouter_api_usa_timeout_reasoning(mock_post):
    mock_post.return_value = _fake_response()
    with mock.patch.dict(
        os.environ,
        {"OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL": "deepseek/deepseek-r1", "OPENROUTER_TIMEOUT": ""},
    ):
        call_openrouter_api(prompt="oi")
    assert mock_post.call_args.kwargs["timeout"] == REASONING_TIMEOUT


@mock.patch("httpx.post")
def test_call_openrouter_api_usa_env_timeout(mock_post):
    mock_post.return_value = _fake_response()
    with mock.patch.dict(
        os.environ,
        {"OPENROUTER_API_KEY": "k", "OPENROUTER_MODEL": "deepseek/deepseek-r1", "OPENROUTER_TIMEOUT": "180"},
    ):
        call_openrouter_api(prompt="oi")
    assert mock_post.call_args.kwargs["timeout"] == 180.0


def test_native_provider_usa_env_timeout():
    with mock.patch.dict(os.environ, {"OPENROUTER_TIMEOUT": "180"}):
        provider = NativeLLMProvider(api_key="k")
    assert provider.timeout == 180.0


def test_native_provider_default_sem_env():
    with mock.patch.dict(os.environ, {"OPENROUTER_TIMEOUT": "", "OPENROUTER_MODEL": "gpt-4o"}):
        provider = NativeLLMProvider(api_key="k")
    assert provider.timeout == DEFAULT_LLM_TIMEOUT
