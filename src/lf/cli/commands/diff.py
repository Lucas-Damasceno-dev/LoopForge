"""Comando CLI 'lf diff' para comparar alterações propostas pelo pipeline contra o workspace."""
from __future__ import annotations

import difflib
import os
import subprocess
from pathlib import Path

import click
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

console = Console()


@click.command(name="diff")
@click.option("--project-id", default="project", help="ID do projeto gerado (padrão: project)")
@click.option("--target-dir", default=".", help="Diretório de trabalho alvo")
@click.option("--interactive", "-i", is_flag=True, help="Exibe o diff em modo comparativo interativo Lado-a-Lado (Side-by-Side)")
def diff_cmd(project_id: str, target_dir: str, interactive: bool):
    """Exibe o diff entre os arquivos propostos pelo LoopForge e o projeto atual."""
    console.print(f"[bold cyan]🔍 Analisando alterações propostas para '{project_id}'...[/bold cyan]\n")

    proposed_dir = Path(f"/tmp/loopforge/{project_id}").resolve()
    target_path = Path(target_dir).resolve()

    if not proposed_dir.exists():
        try:
            res = subprocess.run(["git", "diff"], cwd=target_path, capture_output=True, text=True, timeout=5)
            if res.stdout:
                if interactive:
                    _render_side_by_side_diff("Git Workspace Diff", res.stdout)
                else:
                    syntax = Syntax(res.stdout, "diff", theme="monokai", line_numbers=True)
                    console.print(syntax)
                return
        except Exception:
            pass

        console.print(f"[yellow]Nenhuma alteração temporária encontrada em {proposed_dir}.[/yellow]")
        return

    found_diffs = False
    for p in proposed_dir.rglob("*"):
        if p.is_file():
            rel = p.relative_to(proposed_dir)
            target_file = target_path / rel

            proposed_text = p.read_text(errors="ignore")
            original_text = target_file.read_text(errors="ignore") if target_file.exists() else ""

            if proposed_text != original_text:
                found_diffs = True
                console.print(f"[bold yellow]📄 {rel}:[/bold yellow]")

                if interactive:
                    _render_side_by_side_files(str(rel), original_text, proposed_text)
                else:
                    diff_lines = list(difflib.unified_diff(
                        original_text.splitlines(keepends=True),
                        proposed_text.splitlines(keepends=True),
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                    ))
                    diff_text = "".join(diff_lines)
                    if diff_text:
                        syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
                        console.print(syntax)
                    else:
                        console.print(f"[blue]~ Modificado ({len(original_text)} -> {len(proposed_text)} bytes)[/blue]")

    if not found_diffs:
        console.print("[green]Nenhuma diferença encontrada entre os arquivos propostos e o workspace.[/green]")


def _render_side_by_side_files(filename: str, original: str, proposed: str):
    """Renderiza dois painéis lado a lado comparando versão original vs proposta."""
    orig_syntax = Syntax(original or "// [Arquivo Novo]", "python", theme="monokai", line_numbers=True)
    prop_syntax = Syntax(proposed or "// [Arquivo Deletado]", "python", theme="monokai", line_numbers=True)

    table = Table(title=f"Side-by-Side Diff: {filename}", show_header=True, header_style="bold magenta")
    table.add_column("Workspace Atual (Original)", style="white")
    table.add_column("Proposto pelo LoopForge (Proposto)", style="green")

    table.add_row(
        Panel(orig_syntax, title="Antes", border_style="red"),
        Panel(prop_syntax, title="Depois (Tentativa Agente)", border_style="green"),
    )
    console.print(table)


def _render_side_by_side_diff(title: str, diff_text: str):
    syntax = Syntax(diff_text, "diff", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=title, border_style="cyan"))
