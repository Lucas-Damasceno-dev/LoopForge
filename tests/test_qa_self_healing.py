"""Suíte de testes para a funcionalidade de Self-Healing de Dependências do nó QA."""

from unittest.mock import patch

from lf.pipeline.nodes.qa import _attempt_dependency_self_healing


def test_self_healing_cargo_update_precise(tmp_path):
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text('[package]\nname = "test"\nversion = "0.1.0"\n', encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": ["failed to parse manifest"],
        "output": "error: failed to download replaced source... try cargo update clap_lex@1.1.0 --precise 1.0.0",
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()


def test_self_healing_cargo_edition_2024_bump(tmp_path):
    cargo_toml = tmp_path / "Cargo.toml"
    cargo_toml.write_text('[package]\nname = "test"\nedition = "2024"\n', encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": ["feature `edition2024` is required"],
        "output": "The package requires the Cargo feature called edition2024",
    }

    success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
    assert success is True
    assert 'edition = "2021"' in cargo_toml.read_text(encoding="utf-8")


def test_self_healing_npm_peer_dependencies(tmp_path):
    package_json = tmp_path / "package.json"
    package_json.write_text('{"name": "app", "version": "1.0.0"}', encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": ["npm ERR! code ERESOLVE"],
        "output": "npm ERR! Could not resolve dependency peer dependency conflict",
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()


def test_self_healing_go_mod_tidy(tmp_path):
    """Onda 2 (2.4): go.mod presente + 'no required module' → go mod tidy."""
    go_mod = tmp_path / "go.mod"
    go_mod.write_text("module app\n\ngo 1.21\n", encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": [],
        "output": "build constraints exclude all Go files... no required module provides package",
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()
        assert "go mod tidy" in mock_run.call_args[0][0]


def test_self_healing_pip_instala_pacote_faltante(tmp_path):
    """Onda 2 (2.4): ModuleNotFoundError + requirements.txt → pip install do pacote."""
    req = tmp_path / "requirements.txt"
    req.write_text("requests>=2.0\n", encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": ["ModuleNotFoundError: No module named 'requests'"],
        "output": "",
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()
        assert "pip install requests" in mock_run.call_args[0][0]


def test_self_healing_pip_requirements_completo_quando_sem_pacote_extraido(tmp_path):
    """Onda 2 (2.4): erro pip sem pacote nomeado → instala o requirements.txt inteiro."""
    req = tmp_path / "requirements.txt"
    req.write_text("requests>=2.0\n", encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": ["No matching distribution found"],
        "output": "ERROR: No matching distribution found",
    }

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()
        assert "pip install -r" in mock_run.call_args[0][0]


def test_self_healing_maven_dependency_resolve(tmp_path):
    """Onda 2 (2.4): pom.xml + 'Could not resolve dependencies' → mvn dependency:resolve."""
    pom = tmp_path / "pom.xml"
    pom.write_text("<project></project>", encoding="utf-8")

    harness_res = {
        "passed": 0,
        "errors": [],
        "output": "[ERROR] Failed to execute goal... Could not resolve dependencies",
    }

    with patch("subprocess.run") as mock_run, patch("lf.pipeline.nodes.qa.shutil.which", return_value="/usr/bin/mvn"):
        mock_run.return_value.returncode = 0
        success = _attempt_dependency_self_healing(str(tmp_path), harness_res)
        assert success is True
        mock_run.assert_called_once()
        assert "mvn dependency:resolve" in mock_run.call_args[0][0]
