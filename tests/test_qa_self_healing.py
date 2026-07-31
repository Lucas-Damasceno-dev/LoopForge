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
