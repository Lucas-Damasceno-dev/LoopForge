"""
Resolução do workdir base das runs (AUD-2026-08 / P1-4).

Fonte única da base dos workdirs: o TaskDispatcher constrói o ``output_dir``
de cada task como ``{base}/{run_key}/{task_suffix}``, e a limpeza de artefatos
só age DENTRO dessa base (nunca ``rm -rf`` arbitrário).
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_WORKDIR_BASE = "/tmp/loopforge"


def get_workdir_base() -> str:
    """Base dos workdirs de run.

    Configurável via ``LF_WORKDIR_BASE`` (ex.: testes usam tmp_path). Valor
    vazio/inválido cai no default ``/tmp/loopforge`` para não quebrar o
    comportamento atual.
    """
    raw = os.environ.get("LF_WORKDIR_BASE", DEFAULT_WORKDIR_BASE)
    cleaned = raw.strip().rstrip("/") if raw else ""
    return cleaned or DEFAULT_WORKDIR_BASE


def is_within(parent: str | Path, child: str | Path) -> bool:
    """True se ``child`` é subpath resolvido de ``parent`` (proteção anti path traversal)."""
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False
