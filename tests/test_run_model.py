"""Testes unitários de resolve_model (per-run LLM model, v7).

Precedência: state["llm_model_name"] (override por run) VENCE
OPENROUTER_MODEL → OPENCODE_MODEL → config llm_model → DEFAULT_LLM_MODEL.
"""

import pytest

from lf.pipeline.llm_factory import DEFAULT_LLM_MODEL, resolve_model


def test_state_override_vence_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "env-openrouter")
    monkeypatch.setenv("OPENCODE_MODEL", "env-opencode")
    assert resolve_model({"llm_model_name": "meu-modelo-teste"}) == "meu-modelo-teste"


def test_state_sem_override_usa_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MODEL", "env-openrouter")
    monkeypatch.setenv("OPENCODE_MODEL", "env-opencode")
    assert resolve_model({}) == "env-openrouter"


def test_openrouter_ausente_usa_opencode(monkeypatch):
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setenv("OPENCODE_MODEL", "env-opencode")
    assert resolve_model(None) == "env-opencode"


def test_sem_env_usa_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # sem .loopforge.json → config default
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    assert resolve_model({"llm_model_name": None}) == DEFAULT_LLM_MODEL


def test_resolve_model_sem_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.delenv("OPENCODE_MODEL", raising=False)
    assert resolve_model() == DEFAULT_LLM_MODEL
