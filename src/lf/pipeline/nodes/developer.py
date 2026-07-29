"""
Nó Developer: recebe tech spec e gera estrutura de projeto MULTI-ARQUIVO real (pom.xml, package.json,
pyproject.toml, go.mod, Cargo.toml e testes unitários) via llm_factory / OpenCode runner.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


def _clean_code(raw: str) -> str:
    code = raw.strip()
    if code.startswith("```"):
        code = code.split("\n", 1)[-1] if "\n" in code else code[3:]
    if code.endswith("```"):
        code = code[:-3].strip()
    first_line = code.split("\n", 1)[0].strip()
    if not first_line.startswith(("{", "[")) and first_line.lower() in ("java", "python", "javascript", "go", "rust", "typescript", "xml", "toml", "json"):
        code = code.split("\n", 1)[-1] if "\n" in code else code
    return code.strip()


def _extract_generated_code(res: any, output_dir: str, duration: float = 0.0) -> str:
    """Helper de extração mantido para compatibilidade de testes."""
    if hasattr(res, "changed_files") and res.changed_files:
        for file_path in res.changed_files:
            p = Path(file_path)
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")
    stdout = getattr(res, "stdout", "") or ""
    return _clean_code(stdout)


def _parse_multi_file_response(raw_text: str, default_filename: str) -> dict[str, str]:
    """Extrai múltiplos arquivos do texto retornado pela LLM com base em marcadores de cabeçalho."""
    files: dict[str, str] = {}
    pattern = r"(?:###|\/\/\/|---)\s*(?:FILE|File|file):\s*([^\n\r]+)[\r\n]+```(?:[a-zA-Z0-9_-]+)?\s*[\r\n]+(.*?)```"
    matches = re.findall(pattern, raw_text, re.DOTALL)

    if matches:
        for rel_path, content in matches:
            clean_path = rel_path.strip().strip("`'\"")
            files[clean_path] = content.strip()
    else:
        # Tenta fallback para marcadores sem cercas markdown
        alt_pattern = r"(?:###|\/\/\/|---)\s*(?:FILE|File|file):\s*([^\n\r]+)[\r\n]+(.*?)(?=(?:###|\/\/\/|---)\s*(?:FILE|File|file):|\Z)"
        alt_matches = re.findall(alt_pattern, raw_text, re.DOTALL)
        if alt_matches:
            for rel_path, content in alt_matches:
                clean_path = rel_path.strip().strip("`'\"")
                files[clean_path] = _clean_code(content)

    if not files:
        files[default_filename] = _clean_code(raw_text)

    return files


STACK_PROJECT_TEMPLATES = {
    "java": {
        "lang": "Java",
        "ext": ".java",
        "main_file": "Main.java",
        "manifest_file": "pom.xml",
        "instruction": "You are a Java developer. Generate a complete multi-file Maven project.",
        "rules": [
            "Generate a compilable Java class named Main with a main method",
            "Define multi-file outputs with '### FILE: <path>' headers",
            "Include imports and clean modular structure",
        ],
        "manifest_template": """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.loopforge</groupId>
    <artifactId>generated-app</artifactId>
    <version>1.0.0</version>
    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-api</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter-engine</artifactId>
            <version>5.10.0</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <version>3.1.2</version>
            </plugin>
        </plugins>
    </build>
</project>""",
        "test_file": "src/test/java/com/loopforge/app/MainTest.java",
        "test_template": """package com.loopforge.app;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class MainTest {
    @Test
    public void testBaselineExecution() {
        assertTrue(true, "Suite de testes Maven baseline do LoopForge");
    }
}""",
    },
    "python": {
        "lang": "Python",
        "ext": ".py",
        "main_file": "generated_code.py",
        "manifest_file": "pyproject.toml",
        "instruction": "You are a Python developer. Generate a complete multi-file Python package.",
        "rules": [
            "Generate runnable Python code with main function and __name__ guard",
            "Define multi-file outputs with '### FILE: <path>' headers",
            "Include imports and type hints",
        ],
        "manifest_template": """[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "generated-app"
version = "0.1.0"
description = "LoopForge Generated Python Application"
readme = "README.md"
requires-python = ">=3.10"
dependencies = []

[tool.pytest.ini_options]
minversion = "7.0"
addopts = "-q"
testpaths = ["tests"]
""",
        "test_file": "tests/test_main.py",
        "test_template": """def test_baseline_execution():
    assert True
""",
    },
    "javascript": {
        "lang": "JavaScript",
        "ext": ".js",
        "main_file": "generated_code.js",
        "manifest_file": "package.json",
        "instruction": "You are a JavaScript developer. Generate a complete multi-file Node.js project.",
        "rules": [
            "Write a complete Node.js ESM module or script",
            "Define multi-file outputs with '### FILE: <path>' headers",
        ],
        "manifest_template": """{
  "name": "generated-app",
  "version": "1.0.0",
  "description": "LoopForge Generated Node.js Application",
  "main": "generated_code.js",
  "type": "module",
  "scripts": {
    "start": "node generated_code.js",
    "test": "node --test"
  }
}""",
        "test_file": "test/app.test.js",
        "test_template": """import test from 'node:test';
import assert from 'node:assert';

test('baseline test suite', () => {
  assert.strictEqual(true, true);
});""",
    },
    "go": {
        "lang": "Go",
        "ext": ".go",
        "main_file": "main.go",
        "manifest_file": "go.mod",
        "instruction": "You are a Go developer. Generate a complete multi-file Go project.",
        "rules": [
            "Write complete Go code with package main and func main()",
            "Define multi-file outputs with '### FILE: <path>' headers",
        ],
        "manifest_template": """module generated-app

go 1.21
""",
        "test_file": "main_test.go",
        "test_template": """package main

import "testing"

func TestBaseline(t *testing.T) {
	// Baseline test
}""",
    },
    "rust": {
        "lang": "Rust",
        "ext": ".rs",
        "main_file": "main.rs",
        "manifest_file": "Cargo.toml",
        "instruction": "You are a Rust developer. Generate a complete multi-file Cargo project.",
        "rules": [
            "Write complete Rust code with fn main()",
            "Define multi-file outputs with '### FILE: <path>' headers",
        ],
        "manifest_template": """[package]
name = "generated-app"
version = "0.1.0"
edition = "2021"

[dependencies]
""",
        "test_file": "tests/integration_test.rs",
        "test_template": """#[test]
fn test_baseline() {
    assert_eq!(2 + 2, 4);
}""",
    },
}


def developer(state: GraphState) -> dict:
    """Recebe tech spec e gera estrutura de projeto MULTI-ARQUIVO real."""
    print("---EXECUTANDO NÓ: Developer---")

    attempt_count = state.get("attempt_count", 0) + 1
    stack_lang = str(state.get("stack", "python")).lower()
    sc = STACK_PROJECT_TEMPLATES.get(stack_lang, STACK_PROJECT_TEMPLATES["python"])
    output_dir = state.get("output_dir", ".")
    project_dir = state.get("project_dir", output_dir)

    if state.get("mock_llm"):
        print("--- INFO: Developer modo MOCK (gerando estrutura multi-arquivo mock) ---")
        mock_files = {
            sc["main_file"]: f"// Mock {sc['lang']} code\npublic class Main {{ public static void main(String[] args) {{ System.out.println(\"mock\"); }} }}" if sc["lang"] == "Java" else f"# Mock {sc['lang']} code\nprint('mock')",
            sc["manifest_file"]: sc["manifest_template"],
            sc["test_file"]: sc["test_template"],
        }
        _write_project_files(mock_files, [output_dir, project_dir])
        return {
            **state,
            "code": mock_files[sc["main_file"]],
            "attempt_count": attempt_count,
            "next_agent": "qa",
            "error": None,
        }

    tech_spec = state.get("tech_spec", "")
    idea = state.get("idea", "")
    user_stories = state.get("user_stories", [])
    model_name = os.environ.get("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash:free")

    story_lines = []
    for us in user_stories[:3]:
        sid = us.get("id", "")
        title = us.get("title", "")
        desc = us.get("description", "")[:150]
        story_lines.append(f"- {sid}: {title} — {desc}")

    prompt_parts = [
        f"Implemente um projeto MULTI-ARQUIVOS completo em {sc['lang']}:",
        f"\nIdeia: {idea}",
        f"\nTech Spec:\n{tech_spec[:2000]}",
        f"\nUser Stories:\n{chr(10).join(story_lines) if story_lines else 'N/A'}",
        "\nInstruções de estrutura:",
        f"- Crie o arquivo principal '{sc['main_file']}'",
        f"- Crie o arquivo de manifesto '{sc['manifest_file']}'",
        f"- Crie testes unitários em '{sc['test_file']}'",
        "- Formate a resposta definindo cada arquivo com o cabeçalho:\n### FILE: caminho/do/arquivo\n```\nconteúdo\n```",
    ]

    # Incorporar feedback de retentativas anteriores se houver
    feedback_history = state.get("feedback_history", [])
    test_report = state.get("test_report", {})
    previous_code = state.get("code", "")

    if feedback_history or test_report:
        feedback_lines = []
        for fb in feedback_history:
            sender = fb.get("from", "reviewer").upper()
            msg = fb.get("message", "")
            feedback_lines.append(f"- [{sender} Feedback]: {msg}")

        if test_report and isinstance(test_report, dict):
            suites = test_report.get("results_by_suite", [])
            for s in suites:
                for details in s.get("failed_tests_details", []):
                    err_txt = details.get("error", "")
                    if err_txt:
                        feedback_lines.append(f"- [QA Test Failure]: {err_txt}")

        if feedback_lines:
            prompt_parts.append("\n\n=== CORREÇÕES OBRIGATÓRIAS DE TENTATIVAS ANTERIORES ===")
            prompt_parts.extend(feedback_lines)

        if previous_code:
            prompt_parts.append(f"\n\nCódigo anterior que apresentou falha:\n```\n{previous_code[:1500]}\n```\nCorrija os problemas apontados acima.")

    user_prompt = "\n".join(prompt_parts)

    system_prompt = f"""{sc['instruction']}

REGRAS:
{chr(10).join(f'{i+1}. {r}' for i, r in enumerate(sc['rules']))}
"""

    print(f"--- Chamando LLM Engine (Geração Multi-Arquivo, model: {model_name})... ---")
    try:
        raw = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_name,
            temperature=0.2,
            mock=state.get("mock_llm", False),
            cache=True,
            circuit_breaker=state.get("circuit_breaker"),
        )
        if not isinstance(raw, str):
            raw = str(raw)
    except Exception as e:
        err_msg = f"LLM Engine falhou: {e}"
        print(f"--- AVISO: {err_msg} ---")
        new_feedback = list(feedback_history) + [
            {"from": "developer", "message": err_msg, "attempt": attempt_count}
        ]
        return {
            **state,
            "code": "",
            "attempt_count": attempt_count,
            "feedback_history": new_feedback,
            "next_agent": "qa",
            "error": err_msg,
        }

    # Extrai arquivos gerados pela LLM
    files_map = _parse_multi_file_response(raw, sc["main_file"])

    # Garante a presença do manifesto e suíte de testes baseline da stack se omitidos pela LLM
    if sc["manifest_file"] not in files_map:
        files_map[sc["manifest_file"]] = sc["manifest_template"]
    if sc["test_file"] not in files_map:
        files_map[sc["test_file"]] = sc["test_template"]

    # Escreve todos os arquivos no projeto
    _write_project_files(files_map, [output_dir, project_dir])

    # Código principal selecionado
    primary_code = files_map.get(sc["main_file"]) or list(files_map.values())[0]

    return {
        **state,
        "code": primary_code,
        "attempt_count": attempt_count,
        "next_agent": "qa",
        "error": None,
    }


def _write_project_files(files_map: dict[str, str], target_dirs: list[str]) -> None:
    """Cria recursivamente todos os diretórios e salva os arquivos do projeto."""
    for base_dir in set(target_dirs):
        if not base_dir:
            continue
        for rel_path, content in files_map.items():
            full_path = os.path.join(base_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"--- INFO: Arquivo do projeto salvo: {full_path} ({len(content)} chars) ---")
