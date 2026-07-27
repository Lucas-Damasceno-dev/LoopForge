import click
from lf.cli.commands.init import init_cmd
from lf.cli.commands.plan import plan_cmd
from lf.cli.commands.run import run_cmd
from lf.cli.commands.status import status_cmd


@click.group()
@click.version_option(version="6.0.0", prog_name="loopforge")
def main():
    """LoopForge v6 - Autonomous Agent Governance and Pipeline Orchestrator"""
    pass


main.add_command(init_cmd)
main.add_command(plan_cmd)
main.add_command(run_cmd)
main.add_command(status_cmd)


if __name__ == "__main__":
    main()
