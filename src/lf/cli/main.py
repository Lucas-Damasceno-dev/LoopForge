"""LoopForge CLI Interface — Centraliza os comandos essenciais do ecossistema."""
import click

from lf.cli.commands.audit import audit_cmd
from lf.cli.commands.benchmark import benchmark_cmd
from lf.cli.commands.completion import completion_cmd
from lf.cli.commands.diff import diff_cmd
from lf.cli.commands.explore import explore_cmd
from lf.cli.commands.export import export_cmd
from lf.cli.commands.generate_tests import generate_tests_cmd
from lf.cli.commands.init import init_cmd
from lf.cli.commands.plan import plan_cmd
from lf.cli.commands.pr import pr_cmd
from lf.cli.commands.release import release_cmd
from lf.cli.commands.resume import resume_cmd
from lf.cli.commands.run import run_cmd
from lf.cli.commands.serve import serve_cmd
from lf.cli.commands.status import status_cmd
from lf.cli.commands.studio import studio_cmd


@click.group()
@click.version_option(version="6.0.0", prog_name="loopforge")
def main():
    """LoopForge v6 - Autonomous Agent Governance and Pipeline Orchestrator"""


# Comandos Core
main.add_command(run_cmd)
main.add_command(serve_cmd)
main.add_command(benchmark_cmd)
main.add_command(resume_cmd)
main.add_command(diff_cmd)
main.add_command(explore_cmd)
main.add_command(pr_cmd)
main.add_command(export_cmd)
main.add_command(studio_cmd)
main.add_command(init_cmd)
main.add_command(plan_cmd)
main.add_command(status_cmd)
main.add_command(release_cmd)
main.add_command(completion_cmd)
main.add_command(generate_tests_cmd)
main.add_command(audit_cmd)


if __name__ == "__main__":
    main()
