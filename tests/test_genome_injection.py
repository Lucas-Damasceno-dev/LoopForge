"""Testes da injeção de genoma (ROADMAP 3.2).

Default OFF → prompts intactos (BC). Ligada via env LF_GENOME_INJECTION ou
AdeConfig.genome_injection, anexa a seção "GENOMA DE PROJETO".
"""

from unittest.mock import patch

from lf.config.schema import AdeConfig, AdeMemory
from lf.pipeline.genome_injection import (
    build_genome_summary,
    genome_injection_enabled,
    inject_genome,
)


def test_genome_injection_disabled_by_default():
    """Default: off → prompt inalterado (snapshots de prompt preservados)."""
    prompt = "Você é um CPO. Prompt original."
    assert inject_genome(prompt) == prompt


def test_genome_injection_disabled_via_config(tmp_path, monkeypatch):
    """Config genome_injection=False (default) → prompt intacto mesmo com env ausente."""
    monkeypatch.delenv("LF_GENOME_INJECTION", raising=False)
    assert genome_injection_enabled(AdeConfig()) is False
    assert inject_genome("prompt original") == "prompt original"


def test_genome_injection_enabled_via_env(monkeypatch):
    """Env LF_GENOME_INJECTION=1 liga a injeção mesmo com config default off."""
    monkeypatch.setenv("LF_GENOME_INJECTION", "1")
    assert genome_injection_enabled() is True


def test_genome_injection_enabled_via_config():
    """AdeConfig.genome_injection=True liga a injeção sem env."""
    assert genome_injection_enabled(AdeConfig(genome_injection=True)) is True


def test_inject_genome_appends_section(monkeypatch):
    """Com a injeção ligada e resumo disponível, anexa a seção ao final."""
    monkeypatch.setenv("LF_GENOME_INJECTION", "1")
    with patch("lf.pipeline.genome_injection.build_genome_summary", return_value="12 files, 3 langs, arch: hexagonal"):
        result = inject_genome("Você é um CPO. Prompt original.")

    assert result.startswith("Você é um CPO. Prompt original.")
    assert "=== GENOMA DE PROJETO ===" in result
    assert "12 files, 3 langs, arch: hexagonal" in result


def test_inject_genome_empty_summary_keeps_prompt(monkeypatch):
    """Resumo vazio (falha do scanner) → prompt intacto, sem seção."""
    monkeypatch.setenv("LF_GENOME_INJECTION", "1")
    with patch("lf.pipeline.genome_injection.build_genome_summary", return_value=""):
        assert inject_genome("prompt original") == "prompt original"


def test_build_genome_summary_failure_returns_empty(monkeypatch):
    """Falha no scanner (módulo ausente/erro) → '' e nunca lança."""
    import builtins

    real_import = builtins.__import__

    def broken_import(name, *args, **kwargs):
        if name == "genome":
            raise ImportError("genome indisponível")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken_import)
    assert build_genome_summary(".") == ""


def test_ade_config_genome_memory_defaults():
    """AdeConfig expõe genome_injection=False e memory.cross_project=False por padrão."""
    cfg = AdeConfig()
    assert cfg.genome_injection is False
    assert cfg.memory.cross_project is False
    assert cfg.model_dump()["genome_injection"] is False
    assert cfg.model_dump()["memory"] == {"cross_project": False}


def test_ade_config_genome_memory_override():
    """Config explícita é aceita (PATCH /config no ADE)."""
    cfg = AdeConfig(genome_injection=True, memory=AdeMemory(cross_project=True))
    assert cfg.genome_injection is True
    assert cfg.memory.cross_project is True
