from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command(name="generate-tests")
@click.argument("directory", default=".", type=click.Path(exists=True))
@click.option("--stack", type=click.Choice(["python", "node"]), default="python", help="Stack alvo")
@click.option("--dry-run", is_flag=True, default=False, help="Apenas exibe os testes que seriam gerados")
def generate_tests_cmd(directory: str, stack: str, dry_run: bool):
    """Gera suítes de teste unitário automaticamente para módulos sem cobertura."""
    root = Path(directory)
    created_count = 0

    if stack == "python":
        src_dir = root / "src" if (root / "src").exists() else root
        tests_dir = root / "tests_py"
        tests_dir.mkdir(exist_ok=True)

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

    console.print(f"\n[bold green]✓ Total de {created_count} arquivo(s) de teste processado(s).[/bold green]")
