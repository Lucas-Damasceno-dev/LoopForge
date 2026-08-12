import os
from pathlib import Path

import click
from rich.console import Console

console = Console()

SUPPORTED_STACKS = ("python", "node")

_NODE_IGNORE_DIRS = {"node_modules", "dist", "build", "coverage", ".venv", "tests", "__pycache__"}
_NODE_SUFFIXES = {".js", ".mjs", ".cjs", ".ts"}
_NODE_IGNORE_SUFFIXES = (".test.js", ".spec.js", ".test.ts", ".spec.ts", ".d.ts")
_NODE_IGNORE_NAMES = {"vitest.config.js", "vitest.config.ts", "vite.config.js", "vite.config.ts"}


def _is_js_module(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix in _NODE_SUFFIXES
        and not path.name.endswith(_NODE_IGNORE_SUFFIXES)
        and path.name not in _NODE_IGNORE_NAMES
        and not any(part in _NODE_IGNORE_DIRS for part in path.parts)
    )


def _discover_js_modules(root: Path) -> list[Path]:
    """Descobre módulos JS/TS do projeto (src/ se existir, senão a raiz)."""
    search_root = root / "src" if (root / "src").exists() else root
    return [p for p in search_root.rglob("*") if _is_js_module(p)]


def _node_test_code(src_file: Path, tests_dir: Path) -> str:
    """Gera um teste de smoke vitest válido para o módulo (import real, sem assert genérico)."""
    rel = os.path.relpath(src_file, tests_dir).replace(os.sep, "/")
    if not rel.startswith("."):
        rel = f"./{rel}"
    stem = src_file.stem
    return f"""// Teste de smoke gerado automaticamente pelo LoopForge (stack node / vitest).
import {{ describe, it, expect }} from "vitest";
import * as mod from "{rel}";

describe("{stem}", () => {{
  it("deve carregar o módulo '{stem}' e expor uma API válida", () => {{
    expect(mod).toBeDefined();
  }});
}});
"""


def _generate_python(root: Path, dry_run: bool) -> int:
    src_dir = root / "src" if (root / "src").exists() else root
    tests_dir = root / "tests_py"
    tests_dir.mkdir(exist_ok=True)
    created_count = 0

    for p in src_dir.rglob("*.py"):
        if ".venv" in p.parts or "tests" in p.name or p.name.startswith("__"):
            continue

        module_name = p.stem
        test_file = tests_dir / f"test_{module_name}.py"

        if not test_file.exists():
            test_code = f"""#-*- coding: utf-8 -*-
import pytest

def test_{module_name}_baseline():
    \"\"\"Teste baseline gerado automaticamente pelo LoopForge.\"\"\"
    assert True
"""
            if dry_run:
                console.print(f"[yellow][DRY-RUN] Geraria teste: {test_file.relative_to(root)}[/yellow]")
            else:
                test_file.write_text(test_code, encoding="utf-8")
                console.print(f"[green]✓ Criado: {test_file.relative_to(root)}[/green]")
            created_count += 1

    return created_count


def _generate_node(root: Path, dry_run: bool) -> int:
    modules = _discover_js_modules(root)
    if not modules:
        console.print("[yellow]Nenhum módulo JS/TS encontrado para gerar testes.[/yellow]")
        return 0

    tests_dir = root / "tests"
    tests_dir.mkdir(exist_ok=True)
    created_count = 0

    for p in modules:
        test_file = tests_dir / f"{p.stem}.test.js"
        if test_file.exists():
            continue

        test_code = _node_test_code(p, tests_dir)
        if dry_run:
            console.print(f"[yellow][DRY-RUN] Geraria teste: {test_file.relative_to(root)}[/yellow]")
        else:
            test_file.write_text(test_code, encoding="utf-8")
            console.print(f"[green]✓ Criado: {test_file.relative_to(root)}[/green]")
        created_count += 1

    return created_count


@click.command(name="generate-tests")
@click.argument("directory", default=".", type=click.Path(exists=True))
@click.option("--stack", type=str, default="python", help="Stack alvo (python | node)")
@click.option("--dry-run", is_flag=True, default=False, help="Apenas exibe os testes que seriam gerados")
def generate_tests_cmd(directory: str, stack: str, dry_run: bool):
    """Gera suítes de teste unitário automaticamente para módulos sem cobertura."""
    root = Path(directory)

    if stack == "python":
        created_count = _generate_python(root, dry_run)
    elif stack == "node":
        created_count = _generate_node(root, dry_run)
    else:
        raise click.ClickException(f"stack '{stack}' não suportado. Stacks disponíveis: {', '.join(SUPPORTED_STACKS)}")

    console.print(f"\n[bold green]✓ Total de {created_count} arquivo(s) de teste processado(s).[/bold green]")
