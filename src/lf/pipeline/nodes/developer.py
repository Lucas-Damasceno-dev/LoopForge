"""
Nó Developer: recebe a stack decidida pelo Tech Lead e gera um projeto MULTI-ARQUIVO completo
(código principal, manifesto de dependências e testes unitários).
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from ...config.workdir import is_within
from ...guardrails.circuit_breaker import CircuitBreaker
from ...pipeline.llm_factory import resolve_model
from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode.llm import call_llm_via_opencode, resolve_run_id

logger = logging.getLogger(__name__)


DEFAULT_PROMPT = """Você é um Desenvolvedor Sênior.
Stack definida pelo Tech Lead: {stack}. Gere um projeto completo nesta stack com todos os arquivos necessários (código principal, manifesto de dependências, testes).

REGRAS OBRIGATÓRIAS DE QUALIDADE:
1. Responda no formato multi-arquivos com o cabeçalho '### FILE: caminho/do/arquivo' seguido por bloco de código markdown.
2. Inclua o manifesto de dependências relevante (ex: pyproject.toml, package.json, Cargo.toml, go.mod).
3. Inclua a suíte de testes unitários da stack em diretório apropriado (ex: tests/).
4. TRATAMENTO DE ERROS RIGOROSO: Proibido o uso de `unwrap()`, `expect()` ou `panic!` em Rust (use `anyhow` ou `thiserror`). Proibido `try/except` silencioso ou `pass` em Python.
5. DOCUMENTAÇÃO OBRIGATÓRIA: Toda função, método e struct/classe pública DEVE conter docstrings estruturadas no formato nativo da linguagem ('///' em Rust, docstrings em Python, '/** */' em TypeScript).
6. CONFIGURAÇÃO E AMBIENTE: Inclua um módulo de configuração tipado (ex: `config.py` com `pydantic-settings` ou `config.rs`) e crie o arquivo `.env.example` documentando todas as variáveis de ambiente.
7. CRITÉRIOS DE ACEITAÇÃO: Cada acceptance criterion das user stories DEVE ser coberto por pelo menos 1 teste unitário na suíte. Antes de gerar o código, derive os testes a partir dos critérios de aceitação fornecidos."""


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
        conn.execute(
            "CREATE TABLE IF NOT EXISTS telemetry_events (id TEXT PRIMARY KEY, event_type TEXT, details TEXT, timestamp TEXT)"
        )
        conn.execute(
            "INSERT INTO telemetry_events VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), event_type, json.dumps(details), datetime.now(UTC).isoformat()),
        )
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
    if not first_line.startswith(("{", "[")) and first_line.lower() in (
        "java",
        "python",
        "javascript",
        "go",
        "rust",
        "typescript",
        "xml",
        "toml",
        "json",
    ):
        code = code.split("\n", 1)[-1] if "\n" in code else code
    return code.strip()


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


def _extract_failing_snippets(
    test_report: dict, project_dir: str, previous_code: str, max_chars: int = 1200
) -> list[str]:
    snippets: list[str] = []
    if not isinstance(test_report, dict):
        return snippets

    output_dir = Path(".").resolve()
    base_dirs = [Path(project_dir).resolve(), output_dir]

    main_file_names = {
        "generated_code.py",
        "main.py",
        "generated_code.js",
        "main.go",
        "src/main.rs",
        "src/main/java/Main.java",
    }
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
            res = subprocess.run(
                "go vet ./...", shell=True, cwd=project_dir, capture_output=True, text=True, timeout=15
            )
            if res.returncode != 0:
                errors.append(f"Go vet error: {res.stderr.strip()[:300]}")
        except Exception:
            pass

    # Onda 2 (2.3): cobertura Java — compila os .java gerados com javac num tempdir.
    # Heurística de filtro: apenas erros de SINTAXE contam para o gate ("';' expected",
    # "illegal start", etc.); erros de dependência ("package X does not exist",
    # "cannot find symbol", "cannot access") são IGNORADOS para não gerar falso
    # positivo — quem resolve dependências é o Maven no QA, não o gate.
    java_files = [rel for rel in files_map if rel.endswith(".java")]
    if java_files and shutil.which("javac"):
        import tempfile

        tmpdir = tempfile.mkdtemp(prefix="lf_javac_gate_")
        try:
            srcs = [str(Path(project_dir) / rel) for rel in java_files]
            res = subprocess.run(
                ["javac", "-d", tmpdir, "-proc:none", *srcs], capture_output=True, text=True, timeout=20
            )
            if res.returncode != 0:
                syntax_patterns = (
                    "illegal start",
                    "unexpected type",
                    "';' expected",
                    "reached end of file while parsing",
                    "class, interface, or enum expected",
                    "')' expected",
                    "not a statement",
                )
                syntax_lines = [
                    line for line in (res.stderr or "").splitlines() if any(p in line.lower() for p in syntax_patterns)
                ]
                if syntax_lines:
                    errors.append("Java syntax check error: " + " | ".join(syntax_lines[:3]))
        except Exception:
            pass
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    return errors


# O LangGraph só injeta `config` com a forma `Optional[RunnableConfig]` (string
# exata em langgraph/_internal/_runnable.py, KWARGS_CONFIG_KEYS); `X | None`
# não casa e o parâmetro NÃO é injetado — daí o UP045 suprimido na assinatura.
def developer(state: GraphState, config: Optional[RunnableConfig] = None) -> dict:  # noqa: UP045
    """Gera projeto completo multi-arquivo na stack decidida pelo Tech Lead.

    ``config`` (injetado pelo LangGraph) carrega o ``thread_id`` canônico
    ``run-{run_id}`` (ADR-0003) — usado para o streaming token a token
    (V1.1/ADR-0007) publicar ``token_delta`` com o run_id correto. Sem thread
    ``run-*`` (CLI legada/chamada direta), o streaming fica desligado em
    silêncio — nunca quebra nem atrasa a pipeline.
    """
    print("---EXECUTANDO NÓ: Developer---")

    attempt_count = state.get("attempt_count", 0) + 1
    stack = str(state.get("stack", "python")).lower()
    output_dir = state.get("output_dir", ".")
    project_dir = state.get("project_dir", output_dir)

    # Entrega incremental (v7 5.1): o QA aprovou o slice anterior
    # (slice_status == "passed") → avança para o próximo slice. Retry do MESMO
    # slice mantém slice_status "failed" → NÃO avança (corrige o slice corrente).
    incremental = state.get("incremental_slices", False)
    slices = list(state.get("slices", []) or [])
    slice_index = int(state.get("slice_index", 0) or 0)
    slice_status = state.get("slice_status", "")
    if incremental and slice_status == "passed":
        slice_index += 1
        slice_status = ""
    current_story = None
    if incremental and slices and 0 <= slice_index < len(slices):
        current_story = slices[slice_index].get("story") or {}

    def _slice_extra() -> dict:
        """Propaga o estado do slice em TODOS os retornos (flag off → {})."""
        if not incremental:
            return {}
        return {"slices": slices, "slice_index": slice_index, "slice_status": slice_status}

    default_main = _get_default_filename_by_stack(stack)

    # M-10 (hard-stop = PAUSA, não falha): checa o budget ANTES de qualquer
    # caminho (inclusive o short-circuit mock) para o gate valer em toda run.
    # CircuitBreaker vem do estado como snapshot serializável (canal
    # `circuit_breaker` do GraphState, fonte única ade.yaml via dispatcher).
    cb_data = state.get("circuit_breaker")
    cb = CircuitBreaker.from_snapshot(cb_data) if isinstance(cb_data, dict) else cb_data
    if cb is not None:
        cb.record_iteration()
        if cb.budget_exceeded:
            print("--- CIRCUIT BREAKER: orçamento excedido — run PAUSADA (hard-stop M-10) ---")
            # Interrompe o grafo no próprio nó developer: o checkpoint fica
            # PENDENTE em 'developer' (next != vazio) — a run NÃO falha e pode
            # ser retomada via resume após POST /cost/override (que aplica o
            # novo limite ao CircuitBreaker do estado). Ao retomar, o nó
            # re-executa do topo com o CB atualizado e segue o fluxo normal.
            interrupt(
                {
                    "paused_budget": True,
                    "reason": "budget_exceeded",
                    "node": "developer",
                    "max_usd": cb.max_total_cost,
                    "spent_usd": cb.total_cost,
                }
            )

    if state.get("mock_llm"):
        print(f"--- INFO: Developer modo MOCK (stack decidida pelo TL: {stack}) ---")
        contract_tests = state.get("contract_tests", "")
        mock_files = _generate_mock_project(stack)
        if contract_tests:
            mock_files, skipped_tests_count = _filter_test_paths_from_file_map(mock_files)
            if skipped_tests_count > 0:
                print(
                    f"--- INFO: Developer pulou {skipped_tests_count} arquivo(s) tests/ (contrato de testes ativo) ---"
                )
        _write_project_files(mock_files, [output_dir, project_dir], stack=stack)
        if incremental:
            _bump_slice_attempt(slices, slice_index)
            slice_status = "pending"  # aguarda veredito do QA
        return {
            **state,
            "code": mock_files.get(default_main, list(mock_files.values())[0]),
            "attempt_count": attempt_count,
            "next_agent": "qa",
            "error": None,
            **_slice_extra(),
        }

    tech_spec = state.get("tech_spec", "")
    idea = state.get("idea", "")
    user_stories = state.get("user_stories", [])
    # Modelo LLM da run: override explícito (llm_model_name do estado, ex.
    # campo `model` do POST /api/v1/runs) VENCE env/config (resolve_model).
    model_name = resolve_model(state)

    story_lines = []
    # Modo incremental: só a story do slice corrente entra no prompt (as demais
    # slices entram quando forem a vez delas). Whole-feature: todas as stories.
    stories_for_prompt = [current_story] if current_story is not None else user_stories
    for us in stories_for_prompt:
        story_lines.append(f"- {us.get('id', '')}: {us.get('title', '')}")
        acceptance_criteria = us.get("acceptance_criteria")
        if isinstance(acceptance_criteria, list) and acceptance_criteria:
            story_lines.append("  Critérios de aceitação:")
            for criterion in acceptance_criteria:
                story_lines.append(f"  - {criterion}")

    system_prompt = get_effective_prompt("developer", DEFAULT_PROMPT.format(stack=stack))

    prompt_parts = [
        f"Ideia do Projeto: {idea}",
        f"\nTech Spec:\n{_truncate_tech_spec(tech_spec)}",
        f"\nUser Stories:\n{chr(10).join(story_lines) if story_lines else 'N/A'}",
    ]
    # Contrato de testes do slice corrente (incremental) ou o último gravado
    # pelo Test Writer (whole-feature). O bloco '### MODULES:' funciona com o
    # string scoped — o inventário do slice vem junto no contrato.
    if incremental and current_story is not None and slices:
        contract_tests = str(slices[slice_index].get("contract_tests") or "")
    else:
        contract_tests = state.get("contract_tests", "")
    if contract_tests:
        contract_block = (
            f"\n\n=== CONTRATO DE TESTES (suíte definida pelo Test Writer independente) ===\n"
            f"SEU CÓDIGO DEVE FAZER ESTES TESTES PASSAREM:\n{contract_tests[:2000]}\n"
            "NÃO modifique nem sobrescreva os arquivos em tests/ já fornecidos."
        )
        # P0-2: lê a linha '### MODULES:' do string COMPLETO (antes do truncamento)
        # e converte o inventário em obrigatoriedade explícita de nomenclatura.
        modules_match = re.search(r"### MODULES:\s*(.+)", contract_tests)
        if modules_match:
            module_names = [name.strip() for name in modules_match.group(1).split(",") if name.strip()]
            module_lines = "\n".join(f"- {name}" for name in module_names)
            contract_block += (
                f"\n\n=== MÓDULOS OBRIGATÓRIOS (contrato de testes) ===\n"
                "Seu código DEVE definir estes módulos com estes nomes EXATOS (respeite singular/plural):\n"
                f"{module_lines}\n"
                "Os testes em tests/ importam destes módulos; nomes divergentes causam ModuleNotFoundError na coleta."
            )
        prompt_parts.append(contract_block)

    # 🧬 Injeta o genoma do repositório se disponível (<2s token-optimized summary)
    # Hook opcional: se o módulo 'genome' não existir, pula silenciosamente.
    if importlib.util.find_spec("genome") is not None:
        try:
            from genome import GenomeScanner, render_markdown

            genome_scanner = GenomeScanner(project_dir or ".")
            genome_data = genome_scanner.scan()
            genome_prompt = render_markdown(genome_data)
            if genome_prompt:
                keywords = set(w.lower().strip() for w in f"{idea} {stack}".split() if len(w) > 3)
                filtered_lines = [
                    line
                    for line in genome_prompt.splitlines()
                    if not keywords
                    or any(kw in line.lower() for kw in keywords)
                    or line.startswith("#")
                    or line.startswith("-")
                ]
                selective_genome = "\n".join(filtered_lines[:40])
                if selective_genome:
                    prompt_parts.append(
                        f"\n\n=== CODEBASE GENOME SELETIVO (DNA do Repositório) ===\n{selective_genome}"
                    )
        except Exception as exc:
            print(f"--- INFO: Genome scanner não utilizado nesta etapa: {exc} ---")
            _log_telemetry_event("hook_error", {"hook": "GenomeScanner", "error": str(exc), "node": "developer"})

    # 🧠 Consulta MemoryManager para obter lições aprendidas passadas relevantes
    try:
        from ...memory.manager import MemoryManager, cross_project_enabled

        mem = MemoryManager()
        relevant = mem.search_relevant_lessons(
            query=f"{idea} {stack}",
            stack=stack,
            limit=3,
            cross_project=cross_project_enabled(),
        )
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
            prompt_parts.append(
                f"\n\nCódigo anterior que apresentou falha:\n```\n{previous_code[:1500]}\n```\nCorrija os problemas apontados acima."
            )
            failing_snippets = _extract_failing_snippets(test_report, project_dir, previous_code)
            if failing_snippets:
                prompt_parts.append("\n\nTrechos dos arquivos citados nas falhas:\n" + "\n".join(failing_snippets))

    complexity = state.get("complexity_level", "standard")
    if complexity == "mvp":
        prompt_parts.append(
            "\n=== NÍVEL DE COMPLEXIDADE: MVP ===\nFoque em código funcional e enxuto. Priorize os fluxos principais e mantenha a estrutura direta e sem complexidade desnecessária."
        )
    elif complexity == "advanced":
        prompt_parts.append(
            "\n=== NÍVEL DE COMPLEXIDADE: AVANÇADO ===\nImplemente uma solução completa e robusta, incluindo módulos organizados, tratamento extensivo de erros, funções auxiliares e testes unitários completos."
        )

    user_prompt = "\n".join(prompt_parts)

    print(f"--- Chamando LLM Engine (Stack TL: {stack}, Model: {model_name})... ---")
    # V1.1/ADR-0007: streaming token a token → ADE. O run_id vem do thread_id
    # canônico `run-{uuid}` (ADR-0003); sem ele (CLI legada/chamada direta) o
    # streaming fica desligado — nunca emite delta sintético e nunca falha.
    on_token_delta = None
    if config:
        thread_id = (config.get("configurable") or {}).get("thread_id")
        if isinstance(thread_id, str) and thread_id.startswith("run-"):
            from ...pipeline.llm_factory import TokenDeltaPublisher

            on_token_delta = TokenDeltaPublisher(thread_id[len("run-") :], "developer")
    try:
        raw = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model_name,
            temperature=0.2,
            mock=state.get("mock_llm", False),
            cache=True,
            circuit_breaker=state.get("circuit_breaker"),
            project_root=output_dir,
            on_token_delta=on_token_delta,
            node="developer",
            run_id=resolve_run_id(state, config),
        )
        if not isinstance(raw, str):
            raw = str(raw)
    except Exception as e:
        err_msg = f"LLM Engine falhou: {e}"
        print(f"--- AVISO: {err_msg} ---")
        new_feedback = list(feedback_history) + [{"from": "developer", "message": err_msg, "attempt": attempt_count}]
        # ABORT: erro de LLM (ex.: modelo inválido) NÃO deve seguir para QA com
        # código vazio — o QA reportaria "nenhum teste coletado" e o Developer
        # entraria em loop de retentativa. FINISH é mapeado para END no router.
        return {
            **state,
            "code": "",
            "attempt_count": attempt_count,
            "feedback_history": new_feedback,
            "next_agent": "FINISH",
            "error": err_msg,
            **_slice_extra(),
        }

    files_map = _parse_multi_file_response(raw, default_main)
    # Filtra paths tests/ do código gerado — o contrato (whole-feature ou do
    # slice corrente) é quem manda nos testes; o Developer não sobrescreve.
    if incremental and current_story is not None and slices:
        contract_tests = str(slices[slice_index].get("contract_tests") or "")
    else:
        contract_tests = state.get("contract_tests", "")
    if contract_tests:
        files_map, skipped_tests_count = _filter_test_paths_from_file_map(files_map)
        if skipped_tests_count > 0:
            print(f"--- INFO: Developer pulou {skipped_tests_count} arquivo(s) tests/ (contrato de testes ativo) ---")

    # Limpa subdiretórios antigos do projeto se for um retry para evitar acúmulo de arquiteturas conflitantes.
    # Incremental NÃO limpa: os slices anteriores são acumulados de propósito
    # (regressão é detectada pelo QA comparando o slice novo contra os antigos).
    qa_attempts = state.get("qa_attempt_count", 0)
    if qa_attempts > 0 and not state.get("read_only", False) and not incremental:
        _cleanup_stale_project_dirs([output_dir, project_dir], stack=stack)

    if not state.get("read_only", False):
        _write_project_files(files_map, [output_dir, project_dir], stack=stack)

    # 🔍 Gate Único de Qualidade: Validação sintática AST/Compiler após gravação dos arquivos
    syntax_errors = _check_syntax_and_types(files_map, stack, project_dir)
    if syntax_errors:
        print(f"--- AVISO: Sintaxe inválida detectada pelo AST Gate ({len(syntax_errors)} erros): ---")
        for err in syntax_errors:
            print(f"  - {err}")

    # 🔗 Hook do Agentic Interface Registry: rastreia mudanças e verifica quebras de contrato
    # Hook opcional: se o módulo 'registry' não existir, pula silenciosamente.
    if importlib.util.find_spec("registry") is not None:
        try:
            from registry import RegistryChecker

            reg_checker = RegistryChecker(project_dir or ".")
            breaking_changes = reg_checker.check(agent="developer")
            if breaking_changes:
                print(
                    f"--- AVISO: Agentic Registry detectou {len(breaking_changes)} quebras de contrato no nó Developer! ---"
                )
        except Exception as exc:
            print(f"--- INFO: Agentic Registry hook ignorado: {exc} ---")

    primary_code = files_map.get(default_main) or list(files_map.values())[0]

    # Onda 2 (2.3): gate sintático HARD. Com retries restantes, o nó retorna para
    # si mesmo (developer→developer via EdgeRegistry) com o feedback do gate, para
    # o LLM corrigir ANTES do QA. Esgotado max_retries, segue para o QA mesmo assim
    # (erros registrados no feedback) — evita loop infinito.
    if syntax_errors:
        gate_feedback = {
            "from": "developer",
            "message": "Falha no gate sintático: " + "; ".join(syntax_errors[:5]),
            "attempt": attempt_count,
        }
        max_retries = state.get("max_retries", 3)
        if attempt_count < max_retries:
            return {
                **state,
                "code": primary_code,
                "attempt_count": attempt_count,
                "feedback_history": feedback_history + [gate_feedback],
                "next_agent": "developer",
                "error": None,
                **_slice_extra(),
            }
        feedback_history = feedback_history + [gate_feedback]

    if incremental:
        _bump_slice_attempt(slices, slice_index)
        slice_status = "pending"  # aguarda veredito do QA
    return {
        **state,
        "code": primary_code,
        "attempt_count": attempt_count,
        "feedback_history": feedback_history,
        "next_agent": "qa",
        "error": None,
        **_slice_extra(),
    }


def _bump_slice_attempt(slices: list, slice_index: int) -> None:
    """Incrementa o contador de tentativas do slice corrente (in-place)."""
    if slices and 0 <= slice_index < len(slices):
        slices[slice_index]["attempts"] = int(slices[slice_index].get("attempts", 0) or 0) + 1


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
            "tests/test_main.rs": "#[test]\nfn test_baseline() {\n    assert_eq!(2 + 2, 4);\n}",
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
            "src/test/java/MainTest.java": "import org.junit.jupiter.api.Test;\npublic class MainTest { @Test public void testPass() {} }",
        }
    elif "go" in s:
        return {
            "go.mod": "module generated-app\n\ngo 1.21\n",
            "main.go": 'package main\n\nimport "fmt"\n\nfunc main() {\n\tfmt.Println("Go app")\n}',
            "main_test.go": 'package main\n\nimport "testing"\n\nfunc TestOk(t *testing.T) {\n}',
        }
    else:
        return {
            "pyproject.toml": '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
            "generated_code.py": 'def main():\n    print("Python app")\n\nif __name__ == "__main__":\n    main()',
            "tests/test_main.py": "def test_ok():\n    assert True",
        }


def _find_loopforge_repo_root(path: Path) -> Path | None:
    """Sobe o path procurando um ancestral que seja o repo LoopForge (AGENTS.md + src/lf)."""
    current = Path(path).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "AGENTS.md").exists() and (candidate / "src" / "lf").exists():
            return candidate
    return None


# Manifests de dependência que PERTENCEM a cada linguagem
# (os de OUTRAS stacks são removidos como estrangeiros)
_OWN_MANIFESTS = {
    "python": {"pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "pytest.ini"},
    "go": {"go.mod", "go.sum"},
    "rust": {"Cargo.toml", "Cargo.lock"},
    "java": {"pom.xml", "build.gradle"},
    "javascript": {"package.json", "package-lock.json", "yarn.lock", "tsconfig.json"},
}

# Extensões de código-fonte ESTRANGEIRAS a cada stack (removidas em qualquer nível)
_FOREIGN_SOURCE_EXTS = {
    "python": {".go"},
    "go": {".py"},
    "rust": {".py", ".go", ".java", ".js", ".ts", ".jsx", ".tsx"},
    "java": {".py", ".go", ".rs", ".js", ".ts", ".jsx", ".tsx"},
    "javascript": {".py", ".go", ".rs", ".java"},
}

# Testes estrangeiros dentro de tests/ por linguagem
_FOREIGN_TESTS = {
    "python": {".go", ".rs", ".java", ".js", ".ts"},
    "go": {".py", ".rs", ".java", ".js", ".ts"},
    "rust": {".py", ".go", ".java", ".js", ".ts"},
    "java": {".py", ".go", ".rs", ".js", ".ts"},
    "javascript": {".py", ".go", ".rs", ".java"},
}

# Diretórios de artefatos regeneráveis (build/cache/dependências) — sempre
# removidos na limpeza, inclusive ao final da run (artifacts_only=True).
_ARTIFACT_DIRS = {
    "target",
    "build",
    "dist",
    "test_reports",
    ".pytest_cache",
    "htmlcov",
    ".venv",
    "node_modules",
    "__pycache__",
}

# Diretórios de código-fonte de tentativas anteriores — removidos apenas no
# retry do nó Developer (artifacts_only=False); preservados ao final da run
# (git/PR/diff dependem do código-fonte gerado).
_SOURCE_DIRS = {
    "cmd",
    "internal",
    "src",
    "pkg",
    "migrations",
}


def _is_foreign_file(rel_path: Path, stack: str) -> bool:
    """True se o arquivo (relativo a base_path) é estrangeiro à stack decidida."""
    s = stack.lower()
    own_manifests = _OWN_MANIFESTS.get(s, set())
    name = rel_path.name
    suffix = rel_path.suffix

    # Manifesto de outra stack (ex: go.mod presente numa run de stack python)
    is_foreign_manifest = (
        name in {m for m_list in _OWN_MANIFESTS.values() for m in m_list} and name not in own_manifests
    )
    # Fonte de outra linguagem em qualquer nível sob o target
    is_foreign_source = suffix in _FOREIGN_SOURCE_EXTS.get(s, set())
    # Teste estrangeiro dentro de tests/
    is_foreign_test = "tests" in rel_path.parts and suffix in _FOREIGN_TESTS.get(s, set())
    return is_foreign_manifest or is_foreign_source or is_foreign_test


def _cleanup_stale_project_dirs(target_dirs: list[str], stack: str = "", artifacts_only: bool = False) -> None:
    """Limpa diretórios de código/artefatos de tentativas anteriores (P1-4/AUD-2026-08).

    ``artifacts_only=True`` (fim de run, chamado pelo dispatcher): remove apenas
    artefatos regeneráveis (target/, build/, dist/, test_reports/, .pytest_cache/,
    htmlcov/, .venv/, node_modules/, __pycache__/) e manifestos/fontes estrangeiros
    à stack — o código-fonte gerado fica (PR/diff/explore dependem dele).

    ``artifacts_only=False`` (retry do nó Developer): remove também diretórios de
    código de tentativas anteriores (cmd/, internal/, src/, pkg/, migrations/).

    Segurança: nunca rm -rf arbitrário — cada alvo é validado como subpath do seu
    próprio base_dir antes de remover (is_within), e diretórios dentro do repo
    LoopForge são pulados (proteção dogfooding).
    """
    import shutil

    stale_dirs = _ARTIFACT_DIRS if artifacts_only else (_ARTIFACT_DIRS | _SOURCE_DIRS)
    unique_dirs = list({str(Path(d).resolve()): d for d in target_dirs if d}.values())
    for base_dir in unique_dirs:
        base_path = Path(base_dir).resolve()
        # Proteção dogfooding: nunca limpar o repo LoopForge ou diretórios dentro dele
        if _find_loopforge_repo_root(base_path) is not None:
            continue
        for s_dir in stale_dirs:
            target = base_path / s_dir
            # Subpath seguro: alvo é filho direto do base_dir sendo limpo — valida
            # mesmo assim (defesa contra path traversal em base_dir estranho).
            if not is_within(base_path, target):
                continue
            if target.exists() and target.is_dir():
                try:
                    shutil.rmtree(target)
                    print(f"--- INFO: Limpando diretório antigo de tentativa anterior: {target} ---")
                except Exception as exc:
                    print(f"--- AVISO: Não foi possível remover subdiretório antigo '{target}': {exc} ---")

        # Remove manifestos e fontes estrangeiras à stack decidida (ex: artefatos
        # Go obsoletos de uma run anterior com stack diferente). pom.xml de uma run
        # Java é MANIFESTO PRÓPRIO da stack java — só é removido quando estrangeiro
        # (stack != java), garantindo a remoção do resíduo sem quebrar o Maven do
        # run atual (a própria stack preserva o manifesto que o harness consome).
        for file_path in base_path.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                rel = file_path.relative_to(base_path)  # proteção contra path traversal
            except ValueError:
                continue
            if not is_within(base_path, file_path):
                continue
            if _is_foreign_file(rel, stack):
                try:
                    file_path.unlink()
                    print(f"--- INFO: Removendo artefato estrangeiro à stack '{stack}': {file_path} ---")
                except Exception as exc:
                    print(f"--- AVISO: Não foi possível remover '{file_path}': {exc} ---")


def _write_project_files(files_map: dict[str, str], target_dirs: list[str], stack: str = "") -> None:
    unique_dirs = list({str(Path(d).resolve()): d for d in target_dirs if d}.values())
    for base_dir in unique_dirs:
        base_path = Path(base_dir).resolve()
        # Proteção dogfooding: detecta se o alvo é o repo LoopForge ou está DENTRO
        # dele (sobe o path até achar ancestral com AGENTS.md + src/lf). Se for o
        # caso, pula a escrita inteira — o projeto só deve ser gravado em output_dir.
        is_loopforge_repo = _find_loopforge_repo_root(base_path) is not None
        if is_loopforge_repo:
            print(
                f"--- INFO: Diretório dentro do repo LoopForge protegido: {base_dir} (escrita apenas em output_dir) ---"
            )
            continue

        for rel_path, content in files_map.items():
            full_path = os.path.join(base_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"--- INFO: Arquivo do projeto salvo: {full_path} ({len(content)} chars) ---")

        # Auto-formatação automática da stack antes do QA
        try:
            from lf.runner.harness.runner import TestHarnessRunner

            TestHarnessRunner(stack=stack, auto_format=True).run_auto_formatter(base_dir)
        except Exception:
            pass


def _is_tests_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").strip("/")
    parts = [part for part in normalized.split("/") if part]
    return "tests" in parts


def _filter_test_paths_from_file_map(files_map: dict[str, str]) -> tuple[dict[str, str], int]:
    filtered = {path: content for path, content in files_map.items() if not _is_tests_path(path)}
    return filtered, len(files_map) - len(filtered)
