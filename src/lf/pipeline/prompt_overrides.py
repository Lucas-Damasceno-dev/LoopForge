"""Prompt Central — overrides de prompts dos nós da esteira (ADE PromptPanel).

Persistência em ``.loopforge/prompts_overrides.json`` (escrita atômica).
Cada nó envolve o prompt padrão com ``get_effective_prompt(node, default)``:
override configurado na API substitui o default; sem override, o prompt
embutido do nó prevalece (BC total).

Nós expõem constantes ``DEFAULT_*_PROMPT`` (fonte única) usadas tanto pelo
próprio nó quanto pelo GET /api/v1/prompts para listar os defaults.
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path

from ..config.paths import get_loopforge_dir


def get_prompts_path() -> Path:
    """Caminho do arquivo de overrides (resolvido em call-time, padrão config.py)."""
    return get_loopforge_dir() / "prompts_overrides.json"


def load_overrides(path: str | Path | None = None) -> dict[str, str]:
    """Lê os overrides persistidos. Falha de I/O ou JSON inválido → {} (nunca quebra)."""
    p = Path(path) if path is not None else get_prompts_path()
    try:
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_overrides(overrides: dict[str, str], path: str | Path | None = None) -> None:
    """Persiste overrides de forma atômica (tmp + os.replace)."""
    p = Path(path) if path is not None else get_prompts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(p.parent), prefix=".prompts_overrides-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(overrides, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, p)
    except Exception:
        with contextlib_suppress_exc():
            os.unlink(tmp_name)
        raise


def contextlib_suppress_exc():
    """Pequeno helper para suprimir exceções no cleanup (evita import pesado no topo)."""
    from contextlib import suppress

    return suppress(Exception)


def get_effective_prompt(node: str, default: str, path: str | Path | None = None) -> str:
    """Retorna o prompt efetivo do nó: override persistido ou o default embutido."""
    overrides = load_overrides(path)
    return overrides.get(node, default)


def set_prompt_override(node: str, prompt: str, path: str | Path | None = None) -> dict[str, str]:
    """Salva override do prompt do nó. Retorna o mapeamento atualizado."""
    overrides = load_overrides(path)
    overrides[node] = prompt
    save_overrides(overrides, path)
    return overrides


def delete_prompt_override(node: str, path: str | Path | None = None) -> bool:
    """Remove override do nó. Retorna True se existia e foi removido."""
    overrides = load_overrides(path)
    if node not in overrides:
        return False
    del overrides[node]
    save_overrides(overrides, path)
    return True


# ─── Registry de nós com prompt (fonte única p/ GET /prompts) ───────────────
# Nós que têm system_prompt de persona. qa/devops não entram: não usam LLM
# com prompt de persona (qa roda harness, devops é determinístico).
PROMPT_NODES: tuple[str, ...] = (
    "cpo",
    "pm",
    "tech_lead",
    "test_writer",
    "developer",
    "appsec",
)


def _node_module(node: str):
    """Importa o módulo do nó (lazy, evita ciclo de import com os nós)."""
    import importlib

    return importlib.import_module(f"lf.pipeline.nodes.{node}")


def get_default_prompt(node: str) -> str | None:
    """Retorna o prompt padrão embutido do nó (None se nó não tem constante)."""
    if node not in PROMPT_NODES:
        return None
    module = _node_module(node)
    return getattr(module, "DEFAULT_PROMPT", None)


def list_effective_prompts(path: str | Path | None = None) -> list[dict[str, str]]:
    """Lista [{node, prompt}] com o prompt EFETIVO (override ou default) por nó."""
    overrides = load_overrides(path)
    result: list[dict[str, str]] = []
    for node in PROMPT_NODES:
        default = get_default_prompt(node)
        if default is None:
            continue
        result.append({"node": node, "prompt": overrides.get(node, default)})
    return result
