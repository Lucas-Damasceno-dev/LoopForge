import os
from click.testing import CliRunner
from lf.cli.main import main


def test_cli_e2e_flow(tmp_path):
    os.environ["OPENCODE_MOCK"] = "1"
    runner = CliRunner()

    with runner.isolated_filesystem(temp_dir=tmp_path):
        # 1. init
        res_init = runner.invoke(main, ["init", "--name", "E2E Project", "--stack", "python"])
        assert res_init.exit_code == 0
        assert "Initialized" in res_init.output

        # 2. plan
        res_plan = runner.invoke(main, ["plan", "--vision", "Build a high frequency trading bot"])
        assert res_plan.exit_code == 0
        assert "Generated plan" in res_plan.output

        # 3. status
        res_status = runner.invoke(main, ["status"])
        assert res_status.exit_code == 0
        assert "E2E Project" in res_status.output

        # 4. run
        res_run = runner.invoke(main, ["run"])
        assert res_run.exit_code == 0
        assert "Starting LoopForge run" in res_run.output
