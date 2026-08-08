import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from lf.config.loader import load_config, save_config
from lf.orchestrator.plan_creator import create_plan_from_vision

console = Console()


@click.command(name="plan")
@click.option("--vision", "-v", prompt="Visão do projeto / Especificação", help="Visão geral ou especificação do projeto")
@click.option("--mode", "-m", type=click.Choice(["full", "fast"]), default="full", help="Modo de roteamento: full (hierárquico completo) ou fast (caminho rápido)")
@click.option("--interactive/--no-interactive", default=True, help="Modo interativo com Spec Review Gate")
def plan_cmd(vision: str, mode: str, interactive: bool):
    """Gera o plano de execução com especificação e Spec Review Gate interativo."""
    try:
        cfg = load_config()
    except FileNotFoundError:
        console.print("[red]Nenhum arquivo .loopforge.json encontrado. Execute 'lf init' primeiro.[/red]")
        raise SystemExit(1)

    current_vision = vision
    current_mode = mode

    while True:
        plan = create_plan_from_vision(current_vision, output_dir=".", routing_mode=current_mode)

        # Exibe painel formatado da Especificação & Roteamento
        table = Table(title="[bold cyan]DAG de Tarefas Planejadas[/bold cyan]", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", width=8)
        table.add_column("Persona / Nó", style="green", width=14)
        table.add_column("Descrição da Tarefa", style="white")

        for t in plan.tasks:
            tid = t.get("id", t["id"]) if isinstance(t, dict) else t.id
            ttitle = t.get("title", t["title"]) if isinstance(t, dict) else t.title
            tpersona = t.get("persona", t["persona"]) if isinstance(t, dict) else t.persona
            table.add_row(tid, tpersona.upper(), ttitle)

        mode_badge = "[bold green]FULL-PATH (Hierárquico: CPO → PM → Tech Lead → Dev → QA)[/bold green]" if current_mode == "full" else "[bold yellow]FAST-PATH (Caminho Rápido: Dev → QA)[/bold yellow]"

        panel_content = (
            f"[bold]Visão/Especificação:[/bold] {current_vision}\n"
            f"[bold]Modo de Roteamento:[/bold] {mode_badge}\n"
            f"[bold]Total de Tarefas:[/bold] {len(plan.tasks)}"
        )

        console.clear()
        console.print(Panel(panel_content, title="[bold white]Spec Review Gate — LoopForge v6[/bold white]", border_style="cyan"))
        console.print(table)

        if not interactive or not sys.stdin.isatty():
            cfg.plan = plan
            save_config(cfg)
            console.print("[bold green]Plano salvo com sucesso.[/bold green]")
            break

        console.print("\n[bold yellow]--- SPEC REVIEW GATE ---[/bold yellow]")
        console.print("  [green][1] Aprovar & Salvar Plano[/green]")
        console.print("  [cyan][2] Alternar Roteamento (Full-Path <-> Fast-Path)[/cyan]")
        console.print("  [blue][3] Editar Visão / Especificação[/blue]")
        console.print("  [red][4] Cancelar[/red]")

        choice = Prompt.ask("\nEscolha uma opção", choices=["1", "2", "3", "4"], default="1")

        if choice == "1":
            cfg.plan = plan
            save_config(cfg)
            console.print(f"\n[bold green]✓ Plano aprovado e salvo no .loopforge.json com {len(plan.tasks)} tarefas ({current_mode.upper()}).[/bold green]")
            break
        elif choice == "2":
            current_mode = "fast" if current_mode == "full" else "full"
            console.print(f"[yellow]Modo alterado para {current_mode.upper()}[/yellow]")
        elif choice == "3":
            current_vision = Prompt.ask("Nova visão / especificação do projeto", default=current_vision)
        elif choice == "4":
            console.print("[red]Geração do plano cancelada pelo usuário.[/red]")
            break
