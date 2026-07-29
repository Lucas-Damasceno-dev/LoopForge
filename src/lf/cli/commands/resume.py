"""Comando CLI 'lf resume' para retomar a execução de pipelines do último checkpoint salvo."""
import click
from rich.console import Console
from rich.table import Table

from lf.orchestrator.task_dispatcher import TaskDispatcher

console = Console()


@click.command(name="resume")
@click.option("--project-id", default="project", help="ID do projeto (padrão: project)")
@click.option("--task-id", default="task-1", help="ID da tarefa a retomar (padrão: task-1)")
@click.option("--list", "list_flag", is_flag=True, help="Lista todos os checkpoints gravados disponíveis")
def resume_cmd(project_id: str, task_id: str, list_flag: bool):
    """Retoma uma pipeline falhada ou pausada a partir do último nó bem-sucedido."""
    dispatcher = TaskDispatcher(mock_llm=True)

    if list_flag:
        checkpoints = dispatcher.list_checkpoints()
        if not checkpoints:
            console.print("[yellow]Nenhum checkpoint gravado encontrado.[/yellow]")
            return

        table = Table(title="📌 Checkpoints de Pipeline Disponíveis")
        table.add_column("Thread ID", style="cyan")

        for cp in checkpoints:
            table.add_row(cp)

        console.print(table)
        return

    console.print(f"[bold cyan]⚡ Retomando pipeline do checkpoint '{project_id}-{task_id}'...[/bold cyan]\n")

    try:
        res = dispatcher.resume(project_id=project_id, task_id=task_id)
        if res.get("error"):
            console.print(f"[bold red]❌ Falha ao retomar pipeline: {res['error']}[/bold red]")
        else:
            console.print("[bold green]✅ Pipeline retomada e concluída com sucesso![/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao acessar checkpoint: {e}[/bold red]")
