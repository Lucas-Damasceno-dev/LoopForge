import pytest

from lf.pipeline import llm_factory


def test_call_openrouter_api_streaming_non200_sem_erro_read(monkeypatch):
    """Bug 1: stream com status != 200 lia resp.text SEM resp.read().

    O fake simula o httpx real: acessar `.text` de resposta streaming sem
    `read()` lança RuntimeError("...without having called `read()`"). O fix
    chama `resp.read()` antes — o erro final deve ser o status 429, nunca o
    erro de read().
    """

    class Resp:
        status_code = 429
        _read_called = False

        def read(self):
            self._read_called = True
            return b"rate limited"

        @property
        def text(self):
            if not self._read_called:
                raise RuntimeError("Attempted to access streaming response content, without having called `read()`")
            return "rate limited"

    class FakeStream:
        def __init__(self):
            self._resp = Resp()

        def __enter__(self):
            return self._resp

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, timeout=None):
            self._stream = FakeStream()

        def stream(self, *args, **kwargs):
            return self._stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm_factory, "DEFAULT_OPENROUTER_KEY", "k")
    monkeypatch.setattr("httpx.Client", lambda *a, **k: FakeClient(timeout=k.get("timeout")))
    monkeypatch.setattr("time.sleep", lambda *a, **k: None)

    with pytest.raises(RuntimeError) as excinfo:
        llm_factory.call_openrouter_api(
            "p",
            model="m",
            max_retries=1,
            on_token_delta=lambda _t: None,  # ativa o branch streaming (Bug 1)
        )
    assert "429" in str(excinfo.value), f"erro inesperado: {excinfo.value}"
    assert "read()" not in str(excinfo.value), f"vazou erro de read(): {excinfo.value}"


def test_compress_prompt_vazio_e_truncado():
    assert llm_factory.compress_prompt("") == ""
    txt = "linha 1\n\n\n\nlinha    2 com   espacos\n" + ("x" * 200)
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
