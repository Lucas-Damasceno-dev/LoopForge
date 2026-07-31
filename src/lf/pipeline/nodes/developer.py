"""
Nó Developer: recebe a stack decidida pelo Tech Lead e gera um projeto MULTI-ARQUIVO completo
(código principal, manifesto de dependências e testes unitários).
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode

logger = logging.getLogger(__name__)


def _truncate_tech_spec(spec: str, max_chars: int = 2000) -> str:
    """Preserva seções arquiteturais relevantes antes de truncar para caber no prompt."""
    if len(spec) <= max_chars:
        return spec

    header_pattern = re.compile(r"^\s{0,3}#{2,3}\s+(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
    keywords = (
        "arquitet",
        "estrutur",
        "diretóri",
        "directory",
        "dado",
        "data",
        "component",
        "endpoint",
        "schema",
        "modelo",
    )

    start_idx = None
    for match in header_pattern.finditer(spec):
        title = match.group(1).lower()
        if any(keyword in title for keyword in keywords):
            start_idx = match.start()
            break

    if start_idx is None:
        return spec[:max_chars]

    selected = spec[start_idx : start_idx + max_chars]
    if len(spec) > start_idx + max_chars:
        line_break = selected.rfind("\n")
        if line_break > 0:
            selected = selected[:line_break]
    return selected


def _log_telemetry_event(event_type: str, details: dict) -> None:
    try:
        db_path = Path(".loopforge/telemetry.sqlite").resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE IF NOT EXISTS telemetry_events (id TEXT PRIMARY KEY, event_type TEXT, details TEXT, timestamp TEXT)")
        conn.execute("INSERT INTO telemetry_events VALUES (?, ?, ?, ?)", (str(uuid.uuid4()), event_type, json.dumps(details), datetime.now(UTC).isoformat()))
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Falha ao registrar evento de telemetria: %s", exc)


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


def _extract_failing_snippets(test_report: dict, project_dir: str, previous_code: str, max_chars: int = 1200) -> list[str]:
    snippets: list[str] = []
    if not isinstance(test_report, dict):
        return snippets

    output_dir = Path(".").resolve()
    base_dirs = [Path(project_dir).resolve(), output_dir]

    main_file_names = {"generated_code.py", "main.py", "generated_code.js", "main.go", "src/main.rs", "src/main/java/Main.java"}
    previous_code_normalized = (previous_code or "").strip()

    seen_paths: set[str] = set()
    results_by_suite = test_report.get("results_by_suite", [])
    if not isinstance(results_by_suite, list):
        return snippets

    path_with_line_pattern = re.compile(r"([A-Za-z0-9_\-./]+\.py):(\d+)")
    tests_path_pattern = re.compile(r"(tests/[A-Za-z0-9_\-./]+\.py)")

    for suite in results_by_suite:
        if not isinstance(suite, dict):
            continue
        failed_details = suite.get("failed_tests_details", [])
        if not isinstance(failed_details, list):
            continue

        for detail in failed_details:
            if not isinstance(detail, dict):
                continue
            err_text = detail.get("error") or detail.get("message") or detail.get("test_name") or ""
            if not isinstance(err_text, str) or not err_text:
                continue

            candidate_path = None
            line_no = 1

            match_with_line = path_with_line_pattern.search(err_text)
            if match_with_line:
                candidate_path = match_with_line.group(1)
                line_no = int(match_with_line.group(2))
            else:
                match_tests_path = tests_path_pattern.search(err_text)
                if match_tests_path:
                    candidate_path = match_tests_path.group(1)

            if not candidate_path:
                continue

            normalized_candidate = candidate_path.lstrip("./")
            if normalized_candidate in main_file_names:
                continue
            if normalized_candidate in seen_paths:
                continue

            file_path = None
            for base in base_dirs:
                candidate_abs = (base / normalized_candidate).resolve()
                try:
                    candidate_abs.relative_to(base)
                except ValueError:
                    continue
                if candidate_abs.exists() and candidate_abs.is_file():
                    file_path = candidate_abs
                    break

            if file_path is None:
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            if previous_code_normalized and content.strip() == previous_code_normalized:
                continue

            lines = content.splitlines()
            if not lines:
                continue

            center = max(1, line_no)
            start = max(1, center - 10)
            end = min(len(lines), center + 10)
            excerpt = "\n".join(lines[start - 1 : end])
            header = f"# --- Trecho de {normalized_candidate} (linha {center}) ---"
            snippet = f"{header}\n{excerpt}"

            if len(snippet) > max_chars:
                snippet = snippet[:max_chars].rstrip()

            snippets.append(snippet)
            seen_paths.add(normalized_candidate)

            if len(snippets) >= 2:
                return snippets

    return snippets


def _check_syntax_and_types(files_map: dict[str, str], stack: str, project_dir: str = ".") -> list[str]:
    """Valida sintaxe básica e compilabilidade (AST/cargo check/go vet/node check) antes do QA."""
    import ast
    import shutil
    import subprocess
    errors = []
    s = stack.lower()

    for rel_path, content in files_map.items():
        if rel_path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                errors.append(f"SyntaxError em {rel_path} linha {e.lineno}: {e.msg}")
        elif rel_path.endswith((".js", ".ts")) and shutil.which("node"):
            try:
                res = subprocess.run(["node", "--check", "-"], input=content, text=True, capture_output=True, timeout=5)
                if res.returncode != 0:
                    errors.append(f"Node syntax check error em {rel_path}: {res.stderr.strip()}")
            except Exception:
                pass

    if "rust" in s and (Path(project_dir) / "Cargo.toml").exists() and shutil.which("cargo"):
        try:
            res = subprocess.run("cargo check", shell=True, cwd=project_dir, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                errors.append(f"Cargo check error: {res.stderr.strip()[:300]}")
        except Exception:
            pass
    elif "go" in s and (Path(project_dir) / "go.mod").exists() and shutil.which("go"):
        try:
            res = subprocess.run("go vet ./...", shell=True, cwd=project_dir, capture_output=True, text=True, timeout=15)
            if res.returncode != 0:
                errors.append(f"Go vet error: {res.stderr.strip()[:300]}")
        except Exception:
            pass

    return errors


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
        contract_tests = state.get("contract_tests", "")
        mock_files = _generate_mock_project(stack)
        if contract_tests:
            mock_files, skipped_tests_count = _filter_test_paths_from_file_map(mock_files)
            if skipped_tests_count > 0:
                print(f"--- INFO: Developer pulou {skipped_tests_count} arquivo(s) tests/ (contrato de testes ativo) ---")
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

    story_lines = []
    for us in user_stories[:8]:
        story_lines.append(f"- {us.get('id', '')}: {us.get('title', '')}")
        acceptance_criteria = us.get("acceptance_criteria")
        if isinstance(acceptance_criteria, list) and acceptance_criteria:
            story_lines.append("  Critérios de aceitação:")
            for criterion in acceptance_criteria:
                story_lines.append(f"  - {criterion}")

    system_prompt = f"""Você é um Desenvolvedor Sênior.
Stack definida pelo Tech Lead: {stack}. Gere um projeto completo nesta stack com todos os arquivos necessários (código principal, manifesto de dependências, testes).

REGRAS OBRIGATÓRIAS DE QUALIDADE:
1. Responda no formato multi-arquivos com o cabeçalho '### FILE: caminho/do/arquivo' seguido por bloco de código markdown.
2. Inclua o manifesto de dependências relevante (ex: pyproject.toml, package.json, Cargo.toml, go.mod).
3. Inclua a suíte de testes unitários da stack em diretório apropriado (ex: tests/).
4. TRATAMENTO DE ERROS RIGOROSO: Proibido o uso de `unwrap()`, `expect()` ou `panic!` em Rust (use `anyhow` ou `thiserror`). Proibido `try/except` silencioso ou `pass` em Python.
5. DOCUMENTAÇÃO OBRIGATÓRIA: Toda função, método e struct/classe pública DEVE conter docstrings estruturadas no formato nativo da linguagem ('///' em Rust, docstrings em Python, '/** */' em TypeScript).
6. CONFIGURAÇÃO E AMBIENTE: Inclua um módulo de configuração tipado (ex: `config.py` com `pydantic-settings` ou `config.rs`) e crie o arquivo `.env.example` documentando todas as variáveis de ambiente.
7. CRITÉRIOS DE ACEITAÇÃO: Cada acceptance criterion das user stories DEVE ser coberto por pelo menos 1 teste unitário na suíte. Antes de gerar o código, derive os testes a partir dos critérios de aceitação fornecidos."""

    prompt_parts = [
        f"Ideia do Projeto: {idea}",
        f"\nTech Spec:\n{_truncate_tech_spec(tech_spec)}",
        f"\nUser Stories:\n{chr(10).join(story_lines) if story_lines else 'N/A'}",
    ]
    contract_tests = state.get("contract_tests", "")
    if contract_tests:
        prompt_parts.append(
            f"\n\n=== CONTRATO DE TESTES (suíte definida pelo Test Writer independente) ===\n"
            f"SEU CÓDIGO DEVE FAZER ESTES TESTES PASSAREM:\n{contract_tests[:2000]}\n"
            "NÃO modifique nem sobrescreva os arquivos em tests/ já fornecidos."
        )

    # 🧬 Injeta o genoma do repositório se disponível (<2s token-optimized summary)
    try:
        from genome import GenomeScanner, render_markdown
        genome_scanner = GenomeScanner(project_dir or ".")
        genome_data = genome_scanner.scan()
        genome_prompt = render_markdown(genome_data)
        if genome_prompt:
            keywords = set(w.lower().strip() for w in f"{idea} {stack}".split() if len(w) > 3)
            filtered_lines = [
                line for line in genome_prompt.splitlines()
                if not keywords or any(kw in line.lower() for kw in keywords) or line.startswith("#") or line.startswith("-")
            ]
            selective_genome = "\n".join(filtered_lines[:40])
            if selective_genome:
                prompt_parts.append(f"\n\n=== CODEBASE GENOME SELETIVO (DNA do Repositório) ===\n{selective_genome}")
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
            failing_snippets = _extract_failing_snippets(test_report, project_dir, previous_code)
            if failing_snippets:
                prompt_parts.append(
                    "\n\nTrechos dos arquivos citados nas falhas:\n" + "\n".join(failing_snippets)
                )

    complexity = state.get("complexity_level", "standard")
    if complexity == "mvp":
        prompt_parts.append("\n=== NÍVEL DE COMPLEXIDADE: MVP ===\nFoque em código funcional e enxuto. Priorize os fluxos principais e mantenha a estrutura direta e sem complexidade desnecessária.")
    elif complexity == "advanced":
        prompt_parts.append("\n=== NÍVEL DE COMPLEXIDADE: AVANÇADO ===\nImplemente uma solução completa e robusta, incluindo módulos organizados, tratamento extensivo de erros, funções auxiliares e testes unitários completos.")

    user_prompt = "\n".join(prompt_parts)

    print(f"--- Chamando LLM Engine (Stack TL: {stack}, Model: {model_name})... ---")
    cb_data = state.get("circuit_breaker")
    cb = CircuitBreaker.from_snapshot(cb_data) if isinstance(cb_data, dict) else cb_data
    if cb is not None:
        cb.record_iteration()
        if cb.budget_exceeded:
            print("--- CIRCUIT BREAKER: orçamento excedido, abortando iteração do Developer ---")
            return {
                **state,
                "attempt_count": attempt_count,
                "next_agent": "parallel_audit",
                "error": "Circuit breaker acionado: custo estimado excedeu o limite de budget.",
            }
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
    contract_tests = state.get("contract_tests", "")
    if contract_tests:
        files_map, skipped_tests_count = _filter_test_paths_from_file_map(files_map)
        if skipped_tests_count > 0:
            print(f"--- INFO: Developer pulou {skipped_tests_count} arquivo(s) tests/ (contrato de testes ativo) ---")

    # Limpa subdiretórios antigos do projeto se for um retry para evitar acúmulo de arquiteturas conflitantes
    qa_attempts = state.get("qa_attempt_count", 0)
    if qa_attempts > 0 and not state.get("read_only", False):
        _cleanup_stale_project_dirs([output_dir, project_dir])

    if not state.get("read_only", False):
        _write_project_files(files_map, [output_dir, project_dir])

    # 🔍 Gate Único de Qualidade: Validação sintática AST/Compiler após gravação dos arquivos
    syntax_errors = _check_syntax_and_types(files_map, stack, project_dir)
    if syntax_errors:
        print(f"--- AVISO: Sintaxe inválida detectada pelo AST Gate ({len(syntax_errors)} erros): ---")
        for err in syntax_errors:
            print(f"  - {err}")

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


PROTECTED_ROOT_FILES = {
    "pyproject.toml",
    ".loopforge.json",
    "AGENTS.md",
    "README.md",
    "uv.lock",
}


def _cleanup_stale_project_dirs(target_dirs: list[str]) -> None:
    """Limpa diretórios de código de tentativas anteriores para evitar colisões entre arquiteturas diferentes."""
    import shutil
    stale_dirs = {"cmd", "internal", "src", "pkg", "migrations"}
    unique_dirs = list({str(Path(d).resolve()): d for d in target_dirs if d}.values())
    for base_dir in unique_dirs:
        base_path = Path(base_dir).resolve()
        if (base_path / "AGENTS.md").exists() and (base_path / "src" / "lf").exists():
            continue
        for s_dir in stale_dirs:
            target = base_path / s_dir
            if target.exists() and target.is_dir():
                try:
                    shutil.rmtree(target)
                    print(f"--- INFO: Limpando diretório antigo de tentativa anterior: {target} ---")
                except Exception as exc:
                    print(f"--- AVISO: Não foi possível remover subdiretório antigo '{target}': {exc} ---")


def _write_project_files(files_map: dict[str, str], target_dirs: list[str]) -> None:
    unique_dirs = list({str(Path(d).resolve()): d for d in target_dirs if d}.values())
    for base_dir in unique_dirs:
        base_path = Path(base_dir).resolve()
        is_loopforge_repo = (base_path / "AGENTS.md").exists() and (base_path / "src" / "lf").exists()

        for rel_path, content in files_map.items():
            norm_rel = os.path.normpath(rel_path)
            if is_loopforge_repo and (norm_rel in PROTECTED_ROOT_FILES or norm_rel.startswith(".github")):
                print(f"--- AVISO: Dogfooding Protection ativado: Bloqueada sobrescrita do arquivo do repositório '{rel_path}' ---")
                continue

            full_path = os.path.join(base_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"--- INFO: Arquivo do projeto salvo: {full_path} ({len(content)} chars) ---")


def _is_tests_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    return "tests" in parts


def _filter_test_paths_from_file_map(files_map: dict[str, str]) -> tuple[dict[str, str], int]:
    filtered = {path: content for path, content in files_map.items() if not _is_tests_path(path)}
    return filtered, len(files_map) - len(filtered)
