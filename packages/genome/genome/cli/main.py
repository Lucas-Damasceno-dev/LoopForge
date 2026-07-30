"""Ponto de entrada do CLI 'genome'."""

import click
from genome.cli.cmd_check import check_cmd
from genome.cli.cmd_diff import diff_cmd
from genome.cli.cmd_dump import dump_cmd
from genome.cli.cmd_init import init_cmd
from genome.cli.cmd_query import query_cmd
from genome.cli.cmd_serve import serve_cmd


@click.group()
@click.version_option(version="0.1.0")
def main():
    """🧬 Codebase Genome — Perfil estrutural e semântico multidimensional de codebases."""
    pass


main.add_command(init_cmd)
main.add_command(check_cmd)
main.add_command(diff_cmd)
main.add_command(dump_cmd)
main.add_command(serve_cmd)
main.add_command(query_cmd)

if __name__ == "__main__":
    main()
