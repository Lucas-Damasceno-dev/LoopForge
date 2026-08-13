"""Comando CLI 'lf clean' para purgar workspaces temporários e worktrees órfãs."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

import click
from rich.console import Console

from lf.config.workdir import get_workdir_base
from lf.runner.git.sandbox import GitSandbox

console = Console()


def _format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    if bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val / (1024 * 1024):.1f} MB"


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except Exception:
        pass
    return total


@click.command(name="clean")
@click.option("--all", "clean_all", is_flag=True, default=False, help="Remover todos os workspaces temporários sem filtro de tempo")
@click.option("--older-than-hours", type=float, default=24.0, help="Remover diretórios mais antigos que N horas (padrão: 24h)")
@click.option("--worktrees", is_flag=True, default=False, help="Limpar worktrees órfãs em .slim/worktrees/")
@click.option("--dry-run", is_flag=True, default=False, help="Apenas simular a limpeza e reportar espaço a ser liberado")
def clean_cmd(clean_all: bool, older_than_hours: float, worktrees: bool, dry_run: bool):
    """Limpa diretórios temporários de execuções (/tmp/loopforge) e worktrees órfãs."""
    workdir_base = Path(get_workdir_base()).resolve()
    cutoff_time = time.time() - (older_than_hours * 3600.0)

    console.print(f"[bold cyan]🧹 Executando limpeza do LoopForge ({workdir_base})...[/bold cyan]\n")

    freed_bytes = 0
    removed_count = 0

    if workdir_base.is_dir():
        for item in sorted(workdir_base.iterdir()):
            if not item.is_dir():
                continue
            try:
                mtime = item.stat().st_mtime
                if clean_all or mtime < cutoff_time:
                    size = _dir_size(item)
                    freed_bytes += size
                    removed_count += 1
                    if dry_run:
                        console.print(f"[dim][SIMULAÇÃO][/dim] Seria removido: [yellow]{item.name}[/yellow] ({_format_size(size)})")
                    else:
                        shutil.rmtree(item, ignore_errors=True)
                        console.print(f"  [red]✗[/red] Removido: [white]{item.name}[/white] ({_format_size(size)})")
            except Exception as exc:
                console.print(f"[yellow]Aviso: não foi possível processar {item.name}: {exc}[/yellow]")

    # Limpeza de worktrees caso solicitado ou modo all
    if worktrees or clean_all:
        try:
            sandbox = GitSandbox(".")
            if sandbox.worktree_dir.is_dir():
                for wt in sorted(sandbox.worktree_dir.iterdir()):
                    if wt.is_dir():
                        size = _dir_size(wt)
                        freed_bytes += size
                        removed_count += 1
                        if dry_run:
                            console.print(f"[dim][SIMULAÇÃO][/dim] Worktree: [yellow]{wt.name}[/yellow] ({_format_size(size)})")
                        else:
                            sandbox.cleanup_worktree(wt.name)
                            console.print(f"  [red]✗[/red] Worktree removida: [white]{wt.name}[/white] ({_format_size(size)})")
        except Exception as exc:
            console.print(f"[yellow]Aviso: falha ao limpar worktrees: {exc}[/yellow]")

    action_label = "seriam liberados" if dry_run else "liberados"
    console.print(
        f"\n[bold green]✓ Limpeza concluída:[/bold green] {removed_count} diretório(s), "
        f"[bold]{_format_size(freed_bytes)}[/bold] {action_label}."
    )
