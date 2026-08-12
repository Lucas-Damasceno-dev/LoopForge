"""Testes do suporte a stack node (vitest) no comando 'lf generate-tests'."""

from __future__ import annotations

from click.testing import CliRunner

from lf.cli.commands.generate_tests import generate_tests_cmd


def _run(args):
    return CliRunner().invoke(generate_tests_cmd, args)


def test_generate_tests_node_com_src(tmp_path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "calculator.js").write_text("export function add(a, b) { return a + b; }\n", encoding="utf-8")

    res = _run([str(tmp_path), "--stack", "node"])
    assert res.exit_code == 0

    test_file = tmp_path / "tests" / "calculator.test.js"
    assert test_file.exists()
    content = test_file.read_text(encoding="utf-8")
    assert 'import { describe, it, expect } from "vitest";' in content
    assert 'import * as mod from "../src/calculator.js";' in content
    assert "expect(mod).toBeDefined();" in content
    # Sem placeholder genérico 'assert true' (válido só em pytest).
    assert "assert true" not in content.lower()


def test_generate_tests_node_sem_src_usa_raiz(tmp_path):
    (tmp_path / "index.js").write_text("module.exports = () => 'ok';\n", encoding="utf-8")

    res = _run([str(tmp_path), "--stack", "node"])
    assert res.exit_code == 0

    test_file = tmp_path / "tests" / "index.test.js"
    assert test_file.exists()
    assert '"../index.js"' in test_file.read_text(encoding="utf-8")


def test_generate_tests_node_ignora_node_modules_e_testes(tmp_path):
    (tmp_path / "app.js").write_text("export const x = 1;\n", encoding="utf-8")
    nm = tmp_path / "node_modules" / "dep"
    nm.mkdir(parents=True)
    (nm / "dep.js").write_text("export const y = 2;\n", encoding="utf-8")
    (tmp_path / "app.test.js").write_text("import { it } from 'vitest';\n", encoding="utf-8")

    res = _run([str(tmp_path), "--stack", "node"])
    assert res.exit_code == 0
    assert (tmp_path / "tests" / "app.test.js").exists()
    # node_modules e arquivos de teste não geram novos testes.
    assert not (tmp_path / "tests" / "dep.test.js").exists()
    assert not (tmp_path / "tests" / "app.test.js.test.js").exists()


def test_generate_tests_node_dry_run_nao_cria_arquivo(tmp_path):
    (tmp_path / "app.js").write_text("export const x = 1;\n", encoding="utf-8")

    res = _run([str(tmp_path), "--stack", "node", "--dry-run"])
    assert res.exit_code == 0
    assert "[DRY-RUN]" in res.output
    assert not (tmp_path / "tests" / "app.test.js").exists()


def test_generate_tests_node_sem_modulos_avisa(tmp_path):
    res = _run([str(tmp_path), "--stack", "node"])
    assert res.exit_code == 0
    assert "Nenhum módulo JS/TS encontrado" in res.output


def test_generate_tests_stack_nao_suportado_da_erro(tmp_path):
    res = _run([str(tmp_path), "--stack", "rust"])
    assert res.exit_code != 0
    assert "não suportado" in res.output
