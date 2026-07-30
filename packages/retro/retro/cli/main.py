"""Ponto de entrada do CLI 'retro'."""

import click
from retro.cli.cmd_analyze import analyze_cmd
from retro.cli.cmd_feed import feed_cmd
from retro.cli.cmd_list import list_cmd
from retro.cli.cmd_suggest import suggest_cmd


@click.group()
@click.version_option(version="0.1.0")
def main():
    """🧠 Agentic Retro — Síntese autônoma pós-sessão e realimentação de aprendizados."""
    pass


main.add_command(analyze_cmd)
main.add_command(list_cmd)
main.add_command(feed_cmd)
main.add_command(suggest_cmd)

if __name__ == "__main__":
    main()
