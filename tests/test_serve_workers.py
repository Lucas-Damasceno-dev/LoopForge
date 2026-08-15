"""Validação de --workers no lf serve (multi-processo exige fila redis)."""

import pytest
from click.testing import CliRunner

from lf.cli.commands.serve import serve_cmd


def test_workers_1_ok_sem_redis(monkeypatch):
    monkeypatch.delenv("LF_QUEUE_BACKEND", raising=False)
    # serve_cmd seta LF_API_API_KEY no env do processo (auth liga se presente) —
    # isola p/ não vazar para testes seguintes.
    monkeypatch.setenv("LF_API_API_KEY", "test-key")
    monkeypatch.setenv("LF_API_KEY", "test-key")
    runner = CliRunner()
    # intercepta uvicorn.run p/ não subir servidor de verdade
    import lf.cli.commands.serve as serve_mod

    captured = {}

    def fake_uvicorn(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(serve_mod.uvicorn, "run", fake_uvicorn)
    result = runner.invoke(serve_cmd, ["--workers", "1", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert captured.get("workers") == 1


def test_workers_2_sem_redis_erro(monkeypatch):
    monkeypatch.delenv("LF_QUEUE_BACKEND", raising=False)
    monkeypatch.setenv("LF_API_API_KEY", "test-key")
    monkeypatch.setenv("LF_API_KEY", "test-key")
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--port", "8123"])
    assert result.exit_code != 0
    assert "LF_QUEUE_BACKEND=redis" in result.output


def test_workers_2_com_redis_ok(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("LF_API_API_KEY", "test-key")
    monkeypatch.setenv("LF_API_KEY", "test-key")
    import lf.cli.commands.serve as serve_mod

    captured = {}

    def fake_uvicorn(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(serve_mod.uvicorn, "run", fake_uvicorn)
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert captured.get("workers") == 2


def test_reload_com_workers_erro(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("LF_API_API_KEY", "test-key")
    monkeypatch.setenv("LF_API_KEY", "test-key")
    runner = CliRunner()
    result = runner.invoke(serve_cmd, ["--workers", "2", "--reload", "--port", "8123"])
    assert result.exit_code != 0
    assert "reload" in result.output.lower()
