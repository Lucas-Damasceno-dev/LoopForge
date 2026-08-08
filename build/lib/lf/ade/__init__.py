"""ADE (Automated Development Environment) — SPA embutida do engine.

O build da SPA React (vive em worktree separado) é sincronizado para
`static/dist/` via `scripts/sync_dist.py` e embutido no wheel do `lf`.
O caminho absoluto do dist fica disponível via `SPA_DIST` para o app
mountar a interface (env `LF_SPA_DIST` tem precedência quando definido).
"""

from pathlib import Path

__all__ = ["static", "SPA_DIST"]

static = Path(__file__).parent / "static"
SPA_DIST = static / "dist"
