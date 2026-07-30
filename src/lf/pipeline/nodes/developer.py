"""
Nó Developer: recebe a stack decidida pelo Tech Lead e gera um projeto MULTI-ARQUIVO completo
(código principal, manifesto de dependências e testes unitários).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


def _log_telemetry_event(event_type: str, details: dict) -> None:
    try:
        db_path = Path(".loopforge/telemetry.sqlite").resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS telemetry_events (id TEXT PRIMARY KEY, event_type TEXT, details TEXT, timestamp TEXT)")
        conn.execute("INSERT INTO telemetry_events VALUES (?, ?, ?, ?)", (str(uuid.uuid4()), event_type, json.dumps(details), datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass


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


def _parse_multi_file_response(raw_text: str, default_filename: str = "main.py") -> dict[str, str]:
    """Extrai múltiplos arquivos do texto retornado pela LLM com suporte flexível a variadas cercas Markdown."""
    files: dict[str, str] = {}

    # Padrão 1: ### FILE: path/to/file \n ```lang ... ```
    p1 = r"(?:###|\/\/\/|---|\*\*|##)?\s*(?:FILE|File|file|Path|filename):\s*([^\n\r]+)[\r\n]+```(?:[a-zA-Z0-9_-]+)?\s*[\r\n]+(.*?)```"
    for rel_path, content in re.findall(p1, raw_text, re.DOTALL):
        clean_path = rel_path.strip().strip("`'\"")
        files[clean_path] = content.strip()

    # Padrão 2: ```lang filename=path/to/file \n ... ```
    if not files:
        p2 = r"```(?:[a-zA-Z0-9_-]+)?\s+(?:filename|file|path)=([^\s\n\r`]+)[\r\n]+(.*?)```"
        for rel_path, content in re.findall(p2, raw_text, re.DOTALL):
            clean_path = rel_path.strip().strip("`'\"")
            files[clean_path] = content.strip()

    # Padrão 3: ```lang \n // file: path/to/file \n ... ```
    if not files:
        p3 = r"```(?:[a-zA-Z0-9_-]+)?[\r\n]+(?:\/\/|#|\/\*)\s*(?:file|filename|path):\s*([^\n\r]+)[\r\n]+(.*?)```"
        for rel_path, content in re.findall(p3, raw_text, re.DOTALL):
            clean_path = rel_path.strip().strip("`'\"")
            files[clean_path] = content.strip()

    # Fallback Padrão 4: FILE: sem cercas de código
    if not files:
        p4 = r"(?:###|\/\/\/|---)\s*(?:FILE|File|file):\s*([^\n\r]+)[\r\n]+(.*?)(?=(?:###|\/\/\/|---)\s*(?:FILE|File|file):|\Z)"
        for rel_path, content in re.findall(p4, raw_text, re.DOTALL):
            clean_path = rel_path.strip().strip("`'\"")
            files[clean_path] = _clean_code(content)

    if not files:
        files[default_filename] = _clean_code(raw_text)

    return files


def developer(state: GraphState) -> dict:
    """Gera projeto completo multi-arquivo na stack decidida pelo Tech Lead."""
    print("---EXECUTANDO NÓ: Developer---")

    attempt_count = state.get("attempt_count", 0) + 1
    stack = str(state.get("stack", "python")).lower()
    output_dir = state.get("output_dir", ".")
    project_dir = state.get("project_dir", output_dir)

    default_main = _get_default_filename_by_stack(stack)

    if state.get("mock_llm"):
        print(f"--- INFO: Developer modo MOCK (stack decidida pelo TL: {stack}) ---")
        mock_files = _generate_mock_project(stack)
        _write_project_files(mock_files, [output_dir, project_dir])
        return {
            **state,
            "code": mock_files.get(default_main, list(mock_files.values())[0]),
            "attempt_count": attempt_count,
            "next_agent": "qa",
            "error": None,
        }

    tech_spec = state.get("tech_spec", "")
    idea = state.get("idea", "")
    user_stories = state.get("user_stories", [])
    model_name = os.environ.get("OPENROUTER_MODEL", "inclusionai/ling-3.0-flash:free")

    story_lines = [f"- {us.get('id', '')}: {us.get('title', '')}" for us in user_stories[:3]]

    system_prompt = f"""Você é um Desenvolvedor Sênior.
Stack definida pelo Tech Lead: {stack}. Gere um projeto completo nesta stack com todos os arquivos necessários (código principal, manifesto de dependências, testes).

REGRAS:
1. Responda no formato multi-arquivos com o cabeçalho '### FILE: caminho/do/arquivo' seguido por bloco de código markdown.
2. Inclua o manifesto de dependências relevante (ex: pyproject.toml, package.json, pom.xml, Cargo.toml, go.mod).
3. Inclua a suíte de testes unitários da stack."""

    prompt_parts = [
        f"Ideia do Projeto: {idea}",
        f"\nTech Spec:\n{tech_spec[:2000]}",
        f"\nUser Stories:\n{chr(10).join(story_lines) if story_lines else 'N/A'}",
    ]

    # 🧬 Injeta o genoma do repositório se disponível (<2s token-optimized summary)
    try:
        from genome import GenomeScanner, render_markdown
        genome_scanner = GenomeScanner(project_dir or ".")
        genome_data = genome_scanner.scan()
        genome_prompt = render_markdown(genome_data)
        if genome_prompt:
            prompt_parts.append(f"\n\n=== CODEBASE GENOME (DNA do Repositório) ===\n{genome_prompt}")
    except Exception as exc:
        print(f"--- INFO: Genome scanner não utilizado nesta etapa: {exc} ---")
        _log_telemetry_event("hook_error", {"hook": "GenomeScanner", "error": str(exc), "node": "developer"})

    # 🧠 Consulta MemoryManager para obter lições aprendidas passadas relevantes
    try:
        from ...memory.manager import MemoryManager
        mem = MemoryManager()
        relevant = mem.search_relevant_lessons(query=f"{idea} {stack}", stack=stack, limit=3)
        formatted_lessons = mem.format_lessons_for_prompt(relevant)
        if formatted_lessons:
            prompt_parts.append(f"\n\n{formatted_lessons}")
    except Exception as exc:
        print(f"--- AVISO: Não foi possível carregar memória de lições: {exc} ---")

    # Feedback de retentativas
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

    print(f"--- Chamando LLM Engine (Stack TL: {stack}, Model: {model_name})... ---")
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

    files_map = _parse_multi_file_response(raw, default_main)

    # Verifica se há manifesto ou arquivo de teste gerado
    has_manifest = any(
        f.lower().endswith(("pom.xml", "package.json", "pyproject.toml", "go.mod", "cargo.toml", "build.gradle"))
        for f in files_map
    )
    has_test = any("test" in f.lower() for f in files_map)

    if not has_manifest and not has_test:
        print("--- AVISO: A LLM não gerou manifesto ou testes. O QA irá detectar a ausência e reportar falha. ---")

    if not state.get("read_only", False):
        _write_project_files(files_map, [output_dir, project_dir])

    # 🔗 Hook do Agentic Interface Registry: rastreia mudanças e verifica quebras de contrato
    try:
        from registry import RegistryChecker
        reg_checker = RegistryChecker(project_dir or ".")
        breaking_changes = reg_checker.check(agent="developer")
        if breaking_changes:
            print(f"--- AVISO: Agentic Registry detectou {len(breaking_changes)} quebras de contrato no nó Developer! ---")
    except Exception as exc:
        print(f"--- INFO: Agentic Registry hook ignorado: {exc} ---")

    primary_code = files_map.get(default_main) or list(files_map.values())[0]

    return {
        **state,
        "code": primary_code,
        "attempt_count": attempt_count,
        "next_agent": "qa",
        "error": None,
    }


def _get_default_filename_by_stack(stack: str) -> str:
    s = stack.lower()
    if "rust" in s:
        return "src/main.rs"
    if "javascript" in s or "node" in s or "js" in s:
        return "generated_code.js"
    if "java" in s:
        return "src/main/java/Main.java"
    if "go" in s:
        return "main.go"
    return "generated_code.py"


def _generate_mock_project(stack: str) -> dict[str, str]:
    s = stack.lower()
    if "rust" in s:
        return {
            "Cargo.toml": '[package]\nname = "generated-app"\nversion = "0.1.0"\nedition = "2021"\n[dependencies]\n',
            "src/main.rs": 'fn main() {\n    println!("Hello from Rust");\n}',
            "tests/test_main.rs": '#[test]\nfn test_baseline() {\n    assert_eq!(2 + 2, 4);\n}',
        }
    elif "javascript" in s or "node" in s or "js" in s:
        return {
            "package.json": '{"name":"generated-app","version":"1.0.0","type":"module","scripts":{"test":"node --test"}}',
            "generated_code.js": 'console.log("Hello JS");',
            "test/app.test.js": "import test from 'node:test'; import assert from 'node:assert'; test('ok', () => assert.strictEqual(1, 1));",
        }
    elif "java" in s:
        return {
            "pom.xml": '<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion><groupId>com.lf</groupId><artifactId>app</artifactId><version>1.0</version></project>',
            "src/main/java/Main.java": 'public class Main { public static void main(String[] args) { System.out.println("Java app"); } }',
            "src/test/java/MainTest.java": 'import org.junit.jupiter.api.Test;\npublic class MainTest { @Test public void testPass() {} }',
        }
    elif "go" in s:
        return {
            "go.mod": 'module generated-app\n\ngo 1.21\n',
            "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Go app")\n}',
            "main_test.go": 'package main\n\nimport "testing"\n\nfunc TestOk(t *testing.T) {\n}',
        }
    else:
        return {
            "pyproject.toml": '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "generated_code.py": 'def main():\n    print("Python app")\n\nif __name__ == "__main__":\n    main()',
            "tests/test_main.py": 'def test_ok():\n    assert True',
        }


def _write_project_files(files_map: dict[str, str], target_dirs: list[str]) -> None:
    for base_dir in set(target_dirs):
        if not base_dir:
            continue
        for rel_path, content in files_map.items():
            full_path = os.path.join(base_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"--- INFO: Arquivo do projeto salvo: {full_path} ({len(content)} chars) ---")
