"""Config nova da fila multi-worker (envs LF_QUEUE_BACKEND / LF_REDIS_URL)."""

from lf.api.config import APISettings


def test_queue_backend_default_memory():
    settings = APISettings()
    assert settings.queue_backend == "memory"
    assert settings.redis_url == "redis://localhost:6379"


def test_queue_backend_env_override(monkeypatch):
    monkeypatch.setenv("LF_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("LF_REDIS_URL", "redis://cache:6380")
    settings = APISettings()
    assert settings.queue_backend == "redis"
    assert settings.redis_url == "redis://cache:6380"
