"""Comando para gerar instruções e scripts de autocompletar da CLI LoopForge (bash/zsh/fish)."""
import click
from rich.console import Console

console = Console()

COMPLETION_HELP = """[bold cyan]⚡ LoopForge CLI Shell Completions (Tab Completion)[/bold cyan]

[bold]Bash:[/bold]
  eval "$(_LF_COMPLETE=bash_source lf)" >> ~/.bashrc

[bold]Zsh:[/bold]
  eval "$(_LF_COMPLETE=zsh_source lf)" >> ~/.zshrc

[bold]Fish:[/bold]
  _LF_COMPLETE=fish_source lf > ~/.config/fish/completions/lf.fish
"""


@click.command(name="completion")
@click.option("--shell", type=click.Choice(["bash", "zsh", "fish"]), help="Exibe script direto para a shell informada")
def completion_cmd(shell: str | None):
    """Exibe instruções de autocompletar (Tab completion) para Bash, Zsh e Fish."""
    if shell == "bash":
        print('eval "$(_LF_COMPLETE=bash_source lf)"')
    elif shell == "zsh":
        print('eval "$(_LF_COMPLETE=zsh_source lf)"')
    elif shell == "fish":
        print("_LF_COMPLETE=fish_source lf")
    else:
        console.print(COMPLETION_HELP)
