"""Ponto de entrada do CLI 'registry'."""

import click
from registry.cli.cmd_check import check_cmd
from registry.cli.cmd_serve import serve_cmd
from registry.cli.cmd_track import track_cmd
from registry.cli.cmd_watch import watch_cmd


@click.group()
@click.version_option(version="0.1.0")
def main():
    """🔗 Agentic Interface Registry — Registro central de contratos entre agentes."""
    pass


main.add_command(track_cmd)
main.add_command(check_cmd)
main.add_command(watch_cmd)
main.add_command(serve_cmd)

if __name__ == "__main__":
    main()
