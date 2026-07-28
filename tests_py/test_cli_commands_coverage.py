import pytest
from click.testing import CliRunner
from lf.cli.commands.audit import audit_cmd
from lf.cli.commands.release import release_cmd
from lf.cli.commands.generate_tests import generate_tests_cmd
from lf.cli.commands.status import status_cmd
from lf.cli.commands.init import init_cmd


def test_cli_audit_cmd(tmp_path):
    runner = CliRunner()

    # Test clean directory
    res_clean = runner.invoke(audit_cmd, [str(tmp_path)])
    assert res_clean.exit_code == 0
    assert "Nenhuma vulnerabilidade" in res_clean.output

    # Test directory with vulnerability
    vuln_file = tmp_path / "vuln.py"
    vuln_file.write_text("x = eval('1 + 1')\n", encoding="utf-8")

    res_vuln = runner.invoke(audit_cmd, [str(tmp_path)])
    assert res_vuln.exit_code == 0
    assert "vulnerabilidade(s) encontrada(s)" in res_vuln.output

    # Test JSON output format
    res_json = runner.invoke(audit_cmd, [str(tmp_path), "--format", "json"])
    assert res_json.exit_code == 0
    assert "SEC-002" in res_json.output

    # Test --fix flag
    res_fix = runner.invoke(audit_cmd, [str(tmp_path), "--fix"])
    assert res_fix.exit_code == 0
    assert "autocorrida(s)" in res_fix.output


def test_cli_release_cmd(tmp_path):
    runner = CliRunner()

    # Test --dry-run
    res_dry = runner.invoke(release_cmd, ["6.1.0", "--dry-run"])
    assert res_dry.exit_code == 0
    assert "NOTAS DE RELEASE (DRY RUN)" in res_dry.output

    # Test actual release writing CHANGELOG.md
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res = runner.invoke(release_cmd, ["6.1.0"])
        assert res.exit_code == 0
        assert "lançada e registrada no CHANGELOG.md" in res.output


def test_cli_generate_tests_cmd(tmp_path):
    runner = CliRunner()

    src_dir = tmp_path / "src"
    src_dir.mkdir()
    sample_module = src_dir / "calculator.py"
    sample_module.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    # Test --dry-run
    res_dry = runner.invoke(generate_tests_cmd, [str(tmp_path), "--dry-run"])
    assert res_dry.exit_code == 0
    assert "[DRY-RUN]" in res_dry.output

    # Test actual generation
    res_gen = runner.invoke(generate_tests_cmd, [str(tmp_path)])
    assert res_gen.exit_code == 0
    assert (tmp_path / "tests_py" / "test_calculator.py").exists()


def test_cli_init_and_status(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        res_init = runner.invoke(init_cmd, ["--stack", "python"])
        assert res_init.exit_code == 0

        res_status = runner.invoke(status_cmd)
        assert res_status.exit_code == 0


def test_cli_plan_and_run(tmp_path):
    from lf.cli.commands.plan import plan_cmd
    from lf.cli.commands.run import run_cmd

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(init_cmd, ["--stack", "python"])

        res_plan = runner.invoke(plan_cmd, ["--vision", "Test CLI Vision", "--mode", "fast", "--no-interactive"])
        assert res_plan.exit_code == 0

        res_run = runner.invoke(run_cmd, ["--mock"])
        assert res_run.exit_code == 0
        assert "Starting LoopForge run" in res_run.output

