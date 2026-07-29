"""Comando CLI 'lf diff' para comparar alterações propostas pelo pipeline contra o workspace."""
import os
import subprocess
from pathlib import Path
import click
from rich.console import Console
from rich.syntax import Syntax

console = Console()


@click.command(name="diff")
@click.option("--project-id", default="project", help="ID do projeto gerado (padrão: project)")
@click.option("--target-dir", default=".", help="Diretório de trabalho alvo")
def diff_cmd(project_id: str, target_dir: str):
    """Exibe o diff entre os arquivos propostos pelo LoopForge e o projeto atual."""
    console.print(f"[bold cyan]🔍 Analisando alterações propostas para '{project_id}'...[/bold cyan]\n")

    proposed_dir = Path(f"/tmp/loopforge/{project_id}").resolve()
    target_path = Path(target_dir).resolve()

    if not proposed_dir.exists():
        # Tenta git status/diff se não houver pasta em /tmp
        try:
            res = subprocess.run(["git", "diff"], cwd=target_path, capture_output=True, text=True, timeout=5)
            if res.stdout:
                syntax = Syntax(res.stdout, "diff", theme="monokai")
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
                if not target_file.exists():
                    console.print(f"[green]+ Novo arquivo criado ({len(proposed_text)} bytes)[/green]")
                else:
                    console.print(f"[blue]~ Modificado ({len(original_text)} -> {len(proposed_text)} bytes)[/blue]")

    if not found_diffs:
        console.print("[green]Nenhuma diferença encontrada entre os arquivos propostos e o workspace.[/green]")
