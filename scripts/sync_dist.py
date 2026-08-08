#!/usr/bin/env python3
"""Sincroniza o build da SPA (dist) para o pacote embutido do engine.

Copia o diretório `dist` gerado pelo `npm run build` da SPA React (que vive
em um worktree separado) para `src/lf/ade/static/dist/`, permitindo que o
wheel do `lf` embuta a interface.

Uso:
    python scripts/sync_dist.py <caminho-do-dist>

O argumento é obrigatório — não há default (o caminho do worktree da SPA é
frágil entre máquinas/CI). O script é idempotente: re-executar sobre o mesmo
dist produz o mesmo resultado.

Comportamento:
    1. Valida que o diretório-fonte contém `index.html`.
    2. Copia recursivamente (ignorando sourcemaps `.map`).
    3. Calcula sha256 dos arquivos antes/depois e imprime resumo.
    4. Exit 0 sempre que a cópia for concluída.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

# Pacote destino: src/lf/ade/static/dist (relativo à raiz do repo).
DEST_DIR = Path(__file__).resolve().parent.parent / "src" / "lf" / "ade" / "static" / "dist"


def _manifest(root: Path) -> dict[str, tuple[str, int]]:
    """Mapeia caminho relativo -> (sha256, bytes) para todos os arquivos sob `root`.

    Ignora sourcemaps (`.map`) — o build da SPA os gera apenas em modo dev.
    """
    manifest: dict[str, tuple[str, int]] = {}
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file() or file_path.suffix == ".map":
            continue
        digest = hashlib.sha256(file_path.read_bytes()).hexdigest()
        manifest[str(file_path.relative_to(root))] = (digest, file_path.stat().st_size)
    return manifest


def _summary(manifest: dict[str, tuple[str, int]]) -> str:
    """Formata o resumo de um manifest (N arquivos, bytes totais)."""
    total_bytes = sum(size for _, size in manifest.values())
    return f"{len(manifest)} arquivos, {total_bytes} bytes"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza o dist da SPA para o pacote embutido do engine.",
    )
    parser.add_argument(
        "source",
        help="Diretório do build da SPA (deve conter index.html). Obrigatório.",
    )
    args = parser.parse_args(argv)

    source_dir = Path(args.source).resolve()

    # (a) Valida o diretório-fonte.
    if not source_dir.is_dir():
        print(f"ERRO: diretório-fonte não encontrado: {source_dir}", file=sys.stderr)
        return 1
    if not (source_dir / "index.html").is_file():
        print(f"ERRO: {source_dir} não contém index.html — não é um dist de SPA válido.", file=sys.stderr)
        return 1

    # (b) Copia recursivamente, idempotente, ignorando sourcemaps .map.
    before = _manifest(source_dir)
    shutil.copytree(source_dir, DEST_DIR, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.map"))

    # Remove o .gitkeep do destino — ele só existe para manter o diretório vazio
    # no git; após a sincronização o dist passa a ser o conteúdo real do build.
    gitkeep = DEST_DIR / ".gitkeep"
    if gitkeep.is_file():
        gitkeep.unlink()

    # (c) Compara sha256 antes/depois e imprime o resumo.
    after = _manifest(DEST_DIR)
    match = before == after
    print(f"Fonte  : {source_dir}")
    print(f"Destino: {DEST_DIR}")
    print(f"Antes  : {_summary(before)}")
    print(f"Depois : {_summary(after)}")
    if not match:
        print("AVISO: manifest divergente após a cópia (arquivos com .map foram ignorados).", file=sys.stderr)

    # (d) Exit 0 sempre que a cópia for concluída.
    print("Sincronização concluída.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
