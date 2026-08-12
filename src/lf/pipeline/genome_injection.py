"""Injeção opcional de genoma do projeto nos prompts (ROADMAP 3.2).

Quando habilitada (``AdeConfig.genome_injection`` ou env ``LF_GENOME_INJECTION``),
os prompts de cpo/pm/tech_lead ganham a seção compacta "GENOMA DE PROJETO"
derivada do scanner do pacote externo ``genome`` (codebase_genome). Default
off → prompts atuais intactos (BC total; snapshots não quebram).

Nunca lança: qualquer falha de I/O/import resulta em prompt inalterado.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from ..config.loader import load_ade_config

if TYPE_CHECKING:
    from ..config.schema import AdeConfig

_TRUTHY = {"1", "true", "yes", "on"}

_GENOME_SECTION_HEADER = "=== GENOMA DE PROJETO ==="


def genome_injection_enabled(config: AdeConfig | None = None) -> bool:
    """True se a injeção de genoma está ligada (config ou env LF_GENOME_INJECTION)."""
    env = os.getenv("LF_GENOME_INJECTION", "")
    if env.strip().lower() in _TRUTHY:
        return True
    cfg = config if config is not None else load_ade_config()
    return bool(getattr(cfg, "genome_injection", False))


def build_genome_summary(project_dir: str = ".") -> str:
    """Resumo compacto do genoma do projeto (1 linha). "" em qualquer falha."""
    try:
        from genome import GenomeScanner, render_summary

        genome_data = GenomeScanner(project_dir or ".").scan()
        summary = render_summary(genome_data)
        return summary if summary else ""
    except Exception:
        return ""


def inject_genome(prompt: str, project_dir: str = ".") -> str:
    """Anexa a seção de genoma ao prompt quando habilitado; senão devolve intacto."""
    if not genome_injection_enabled():
        return prompt
    summary = build_genome_summary(project_dir)
    if not summary:
        return prompt
    return f"{prompt}\n\n{_GENOME_SECTION_HEADER}\n{summary}"
