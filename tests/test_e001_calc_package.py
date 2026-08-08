"""US008 — Pacote instalável via pip."""

import importlib.metadata as metadata
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from lf.cli.main import main

REPO_ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def _make_venv(tmp_path) -> Path:
    venv = tmp_path / "venv"
    proc = subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return venv


def test_us008_pip_install_termina_com_sucesso(tmp_path):
    venv = _make_venv(tmp_path)
    install = subprocess.run(
        [str(venv / "bin" / "pip"), "install", "--no-input", "--no-deps", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert install.returncode == 0, install.stderr

    check = subprocess.run(
        [str(venv / "bin" / "python"), "-c", "import lf; print(lf.__file__)"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert check.returncode == 0, check.stderr
    assert "site-packages" in check.stdout


def test_us008_comando_lf_reconhecido_no_path():
    eps = metadata.entry_points()
    scripts = {ep.name: ep.value for ep in eps.select(group="console_scripts")}
    assert "lf" in scripts
    assert scripts["lf"] == "lf.cli.main:main"


def test_us008_instalacao_limpa_executa_calc(tmp_path):
    venv = _make_venv(tmp_path)
    install = subprocess.run(
        [str(venv / "bin" / "pip"), "install", "--no-input", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert install.returncode == 0, install.stderr

    run = subprocess.run(
        [str(venv / "bin" / "lf"), "calc", "2 + 2"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.strip() == "4"


def test_us008_versao_relatada_coincide_com_pacote():
    pyproject_version = metadata.version("lf")
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert pyproject_version in result.output
