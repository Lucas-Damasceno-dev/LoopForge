"""
Comando CLI 'lf pr': Inicializa repositório Git no diretório de saída, realiza commit
e cria Pull Request no GitHub com as alterações geradas pelo LoopForge.
"""
from __future__ import annotations

import os
import subprocess
import click
from rich.console import Console

console = Console()


def create_git_pr(project_dir: str, idea: str = "LoopForge Feature", session_id: str = "run") -> dict:
    """Inicializa repositório git, faz commit e tenta abrir PR via GitHub CLI."""
    if not project_dir or not os.path.exists(project_dir):
        return {"status": "error", "message": "Diretório do projeto não encontrado."}

    try:
        # 1. git init
        if not os.path.exists(os.path.join(project_dir, ".git")):
            subprocess.run(["git", "init"], cwd=project_dir, capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "LoopForge Bot"], cwd=project_dir, capture_output=True)
            subprocess.run(["git", "config", "user.email", "bot@loopforge.dev"], cwd=project_dir, capture_output=True)

        # 2. git add & commit
        subprocess.run(["git", "add", "."], cwd=project_dir, capture_output=True, check=True)

        commit_msg = f"feat: código gerado por LoopForge run {session_id}"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=project_dir, capture_output=True)

        # 3. Tenta gh pr create se gh CLI instalado
        pr_url = None
        try:
            gh_check = subprocess.run(["gh", "--version"], capture_output=True)
            if gh_check.returncode == 0:
                pr_res = subprocess.run(
                    ["gh", "pr", "create", "--title", f"feat: {idea[:60]}", "--body", "Código gerado autonomamente pelo LoopForge v6."],
                    cwd=project_dir,
                    capture_output=True,
                    text=True,
                )
                if pr_res.returncode == 0:
                    pr_url = pr_res.stdout.strip()
        except Exception:
            pass

        return {
            "status": "success",
            "commit_msg": commit_msg,
            "pr_url": pr_url,
            "project_dir": project_dir,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@click.command(name="pr")
@click.option("--dir", "project_dir", default=".", help="Diretório do projeto para commitar e abrir PR")
@click.option("--idea", default="LoopForge Feature", help="Título/Ideia do PR")
def pr_cmd(project_dir: str, idea: str):
    """Inicializa repositório Git, commita alterações e abre um Pull Request no GitHub."""
    console.print(f"[bold cyan]🚀 Inicializando Git e criando PR em '{project_dir}'...[/bold cyan]")
    res = create_git_pr(project_dir=project_dir, idea=idea)

    if res["status"] == "success":
        console.print(f"[bold green]✔ Commit criado:[/bold green] {res['commit_msg']}")
        if res.get("pr_url"):
            console.print(f"[bold gold1]🔗 Pull Request criado:[/bold gold1] {res['pr_url']}")
        else:
            console.print("[dim]ℹ Repositório git commitado localmente. Configure remotos para 'gh pr create'.[/dim]")
    else:
        console.print(f"[bold red]✖ Falha ao criar PR:[/bold red] {res['message']}")
