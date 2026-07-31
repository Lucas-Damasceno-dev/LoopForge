import types

from lf.pipeline import llm_factory


def test_compress_prompt_vazio_e_truncado():
    assert llm_factory.compress_prompt("") == ""
    txt = ("linha 1\n\n\n\nlinha    2 com   espacos\n" + ("x" * 200))
    out = llm_factory.compress_prompt(txt, max_chars=80)
    assert "[... PROMPT COMPRESSÃO SEMÂNTICA LOOPFORGE ...]" in out
    assert "linha 2 com espacos" in out


def test_call_openrouter_api_streaming(monkeypatch):
    class Resp:
        status_code = 200
        text = (
            'data: {"choices":[{"delta":{"content":"ola "}}]}\n'
            'data: {"choices":[{"delta":{"content":"mundo"}}],"usage":{"prompt_tokens":3,"completion_tokens":2}}\n'
            "data: [DONE]\n"
        )

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm_factory, "DEFAULT_OPENROUTER_KEY", "k")
    monkeypatch.setattr("httpx.post", lambda *a, **k: Resp())

    text, usage = llm_factory.call_openrouter_api("p", model="m", max_retries=0)
    assert text == "ola mundo"
    assert usage == {"prompt_tokens": 3, "completion_tokens": 2}


def test_call_openrouter_api_retry_ate_sucesso(monkeypatch):
    calls = {"n": 0}

    class Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}

    def fake_post(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transiente")
        return Resp()

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm_factory, "DEFAULT_OPENROUTER_KEY", "k")
    monkeypatch.setattr("httpx.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda *_a, **_k: None)

    text, usage = llm_factory.call_openrouter_api("p", model="m", max_retries=1)
    assert text == "ok"
    assert usage["prompt_tokens"] == 1
    assert calls["n"] == 2


def test_openrouter_provider_schema_fallback_para_texto(monkeypatch):
    monkeypatch.setattr(llm_factory, "call_openrouter_api", lambda *_a, **_k: ("not-json", {"prompt_tokens": 1, "completion_tokens": 1}))
    monkeypatch.setattr(llm_factory.CostTracker, "track", lambda *_a, **_k: 0.0)
    provider = llm_factory.OpenRouterProvider()
    out = provider.generate("sys", "usr", model="x", schema_model=dict)
    assert out == "not-json"


def test_execute_llm_provider_desconhecido_faz_fallback_opencode(monkeypatch):
    monkeypatch.setattr(
        llm_factory.OpenCodeCLIProvider,
        "generate",
        lambda self, **kwargs: f"ok:{kwargs['user_prompt']}",
    )
    out = llm_factory.execute_llm("s", "u", provider_name="inexistente")
    assert out == "ok:u"


def test_cost_tracker_fallback_sem_tiktoken(monkeypatch, tmp_path):
    orig_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "tiktoken":
            raise ImportError("no")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)
    db = tmp_path / "telemetry.sqlite"
    tracker = llm_factory.CostTracker(db)
    cost = tracker.track("modelo-nao-mapeado", "abcd" * 10, "xy" * 10)
    assert isinstance(cost, float)
    assert cost > 0
