"""
Nó QA: executa testes reais via harness e gera relatório estruturado,
sem mutação direta de estado e sem reportar PASS falso para 0 testes.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ...pipeline.state import GraphState


def compute_qa_fingerprint(code: str, test_report: dict) -> str:
    """Calcula hash SHA256 da iteração (código + falhas de teste) para detecção de estagnação."""
    import hashlib

    summary = test_report.get("summary", {}) if isinstance(test_report, dict) else {}
    failed_tests = summary.get("tests_failed", 0)
    errors = summary.get("errors", [])
    raw = f"code_len:{len(code)}|code_hash:{hashlib.sha256(code.encode()).hexdigest()[:16]}|failed:{failed_tests}|errors:{errors}"
    return hashlib.sha256(raw.encode()).hexdigest()


def qa(state: GraphState) -> dict:
    """Analisa código gerado, executa testes e gera relatório."""
    print("---EXECUTANDO NÓ: QA---")

    code = state.get("code", "")
    project_dir = state.get("project_dir", os.getcwd())
    # QA executa o harness no diretório do produto (output_dir) para não coletar testes do próprio repo; fallback para project_dir.
    product_dir = state.get("output_dir") or project_dir
    now_iso = datetime.now(UTC).isoformat()
    report_id = f"EXEC-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    feedback_history = list(state.get("feedback_history", []))

    # Entrega incremental (v7 5.1): slice corrente para classificação e gate de
    # cobertura (flag off → variáveis vazias, comportamento byte-idêntico).
    incremental = state.get("incremental_slices", False)
    slices = list(state.get("slices", []) or [])
    slice_index = int(state.get("slice_index", 0) or 0)
    current_story = None
    if incremental and slices and 0 <= slice_index < len(slices):
        current_story = slices[slice_index].get("story") or {}

    if not code and not state.get("mock_llm"):
        print("--- AVISO: QA pulando testes — nenhum código foi gerado pelo Developer ---")
        fail_report = _build_report_from_harness(
            report_id,
            now_iso,
            {"passed": 0, "total": 0, "errors": ["Nenhum código para testar"], "duration_ms": 0},
            user_story_id="US000",
        )
        qa_attempt = state.get("qa_attempt_count", 0) + 1
        new_feedback = feedback_history + [
            {"from": "qa", "message": "Nenhum código gerado — Developer falhou", "timestamp": now_iso}
        ]
        print(
            f"--- AVISO: Testes falharam (tentativa {qa_attempt}/{state.get('max_retries', 3)}). Reportando ao Developer. ---"
        )
        slice_payload: dict = {}
        if incremental:
            slice_payload = _slice_fail_payload(slices, slice_index, current_story, fail_report)
        return {
            **state,
            "test_report": fail_report,
            "qa_attempt_count": qa_attempt,
            "feedback_history": new_feedback,
            "next_agent": "developer",
            **slice_payload,
        }

    if state.get("mock_llm"):
        print("--- INFO: QA modo MOCK ---")
        report = _mock_report(report_id, now_iso)
        if incremental:
            # Slice mock: aprovado por construção — mantém o E2E determinístico.
            slice_id = (current_story or {}).get("id", "US000")
            slice_test_report = {
                **report,
                "slice_id": slice_id,
                "slice_failed": 0,
                "regression_failed": 0,
                "test_scope": "slice",
            }
            slices[slice_index]["status"] = "passed"
            slices[slice_index]["test_report"] = slice_test_report
            return {
                **state,
                "test_report": report,
                "slice_test_report": slice_test_report,
                "slice_status": "passed",
                "slices": slices,
                "test_scope": "slice",
                "next_agent": "parallel_audit",
            }
        return {**state, "test_report": report, "next_agent": "parallel_audit"}

    # Fase 1: Executar harness real no projeto
    harness_result = _run_harness(product_dir, state.get("stack", ""), output_dir=state.get("output_dir", "."))

    # Fase 2: Gerar relatório estruturado via OpenCode (com fallback resiliente para o harness)
    user_stories = state.get("user_stories", [])
    # Modo incremental: user_story_id vem do slice corrente (não da story 0).
    if current_story is not None:
        user_story_id = current_story.get("id", "US001")
    else:
        user_story_id = user_stories[0].get("id", "US001") if user_stories else "US001"

    # 🩹 Self-Healing MVP de Dependências: se falhar por versão incompatível, tenta auto-fixar
    if (harness_result.get("passed", 0) == 0 or harness_result.get("errors")) and _attempt_dependency_self_healing(
        product_dir, harness_result
    ):
        print("--- INFO: Re-executando Test Harness após Self-Healing de dependências ---")
        harness_result = _run_harness(product_dir, state.get("stack", ""), output_dir=state.get("output_dir", "."))

    # Onda 2 (2.1): gate de auto-formatação — arquivos fora do padrão do formatador
    # da stack (ruff format --check, cargo fmt --check, gofmt, prettier) viram erro
    # de QA com feedback corrigível pro Developer. O auto-fix do runner formata em
    # memória p/ os testes rodarem, mas a entrega ainda conta como FAIL (o código
    # deve chegar formatado; formatar por fora é vício que o Developer precisa corrigir).
    format_issues = harness_result.get("format_issues")
    if isinstance(format_issues, list) and format_issues:
        sample = "; ".join(str(f) for f in format_issues[:5])
        format_err = (
            f"Auto-formatação pendente: {len(format_issues)} arquivo(s) não formatados "
            f"({sample}). Rode o formatador da stack (ruff format, cargo fmt, gofmt, "
            "prettier) antes de entregar — o código deve chegar formatado no QA."
        )
        harness_result.setdefault("errors", []).append(format_err)
        print(f"--- AVISO: Gate de formatação falhou ({len(format_issues)} arquivo(s)) ---")

    print(
        f"--- INFO: Harness executado (passou={harness_result.get('passed')}, erros={len(harness_result.get('errors', []))}) ---"
    )

    report = _build_report_from_harness(report_id, now_iso, harness_result, user_story_id)

    if not isinstance(report, dict) or "summary" not in report:
        report = _build_report_from_harness(report_id, now_iso, harness_result, user_story_id)

    # Se harness falhou ou a compilação/testes falharam, garante que o summary e feedback contenham o erro real
    raw_output = harness_result.get("output", "").strip()
    harness_success = harness_result.get("success", False)
    harness_failed = harness_result.get("failed", 0)
    harness_passed = harness_result.get("passed", 0)

    if not harness_success or harness_failed > 0 or harness_passed == 0 or harness_result.get("errors"):
        report["summary"]["status"] = "FAIL"
        report["summary"]["tests_passed"] = harness_passed
        report["summary"]["tests_failed"] = max(1, harness_failed, len(harness_result.get("errors", [])))

    report["id"] = report_id
    report["execution_timestamp"] = now_iso
    report.setdefault("summary", {})["duration_seconds"] = harness_result.get("duration_ms", 0) / 1000.0

    # Gate determinístico de cobertura de critérios: cada acceptance criterion precisa de ao menos 1 teste passando.
    # Modo incremental: soma SÓ os critérios do slice corrente (o gate whole-feature
    # com todas as stories falharia slices que ainda não foram implementados).
    if current_story is not None:
        story_criteria = current_story.get("acceptance_criteria")
        total_criteria = len(story_criteria) if isinstance(story_criteria, list) else 0
    else:
        total_criteria = sum(
            len(us.get("acceptance_criteria") or [])
            for us in user_stories
            if isinstance(us.get("acceptance_criteria"), list)
        )
    passed = report.get("summary", {}).get("tests_passed", 0)
    criteria_coverage_feedback = ""
    contract_tests_feedback = ""
    if total_criteria > 0 and passed < total_criteria:
        report["summary"]["status"] = "FAIL"
        report["summary"]["tests_failed"] = max(report["summary"].get("tests_failed", 1), total_criteria - passed)
        criteria_coverage_feedback = (
            f"- [QA Cobertura de Critérios]: {total_criteria} acceptance criteria definidos, "
            f"mas apenas {passed} teste(s) passaram. Cada critério deve ter pelo menos 1 teste (regra 7)."
        )
    contract_tests = state.get("contract_tests")
    if contract_tests:
        contract_test_files = _find_contract_test_files(product_dir, state.get("stack", ""))
        if not contract_test_files:
            report["summary"]["status"] = "FAIL"
            report["summary"]["tests_failed"] = max(report["summary"].get("tests_failed", 1), 1)
            contract_tests_feedback = (
                "- [QA Contrato de Testes]: o contrato de testes definido pelo Test Writer não foi encontrado em tests/. "
                "O código deve fazer os testes-contrato passarem."
            )

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"test_report_{report_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Test report salvo em {path} ---")

    is_pass = (
        report.get("summary", {}).get("status") == "PASS" and report.get("summary", {}).get("tests_failed", 1) == 0
    )
    next_agent = "parallel_audit" if is_pass else "developer"

    qa_attempt = state.get("qa_attempt_count", 0)
    new_feedback = feedback_history
    if not is_pass:
        qa_attempt += 1
        print(
            f"--- AVISO: Testes falharam (tentativa {qa_attempt}/{state.get('max_retries', 3)}). Reportando ao Developer. ---"
        )
        no_tests_found = report.get("summary", {}).get("no_tests_found", False)
        failed_cnt = report.get("summary", {}).get("tests_failed", 1)
        stack = state.get("stack", "python")

        if no_tests_found:
            # Nenhum teste coletado: feedback preciso para o developer criar/ajustar tests/
            harness_cmd = harness_result.get("command") or "(comando não detectado)"
            msg = (
                f"FALHA NO QA (Tentativa {qa_attempt}): NENHUM TESTE COLETADO — "
                f"crie/ajuste tests/ para a stack {stack}; verifique imports e estrutura. "
                f"Comando do harness: {harness_cmd}"
            )
            # P1-3: anexa o que o harness realmente disse (stderr/stdout) para o
            # Developer enxergar a causa (ex.: ImportError) em vez do texto genérico.
            if raw_output:
                output_snippet = raw_output[-500:].replace("\n", " ").strip()
                msg = f"{msg}\nSaída do harness:\n{output_snippet}"
        else:
            # Extrai os detalhes reais do erro do compilador/harness
            err_list = harness_result.get("errors", [])
            if err_list:
                err_details = "; ".join(err_list[:3])
                # Anexa diagnóstico estruturado por teste (test_name + erro) quando disponível
                structured = []
                suites = report.get("results_by_suite", [])
                if isinstance(suites, list):
                    for suite in suites:
                        if not isinstance(suite, dict):
                            continue
                        for detail in suite.get("failed_tests_details", []):
                            if not isinstance(detail, dict):
                                continue
                            test_name = detail.get("test_name") or detail.get("name") or "teste"
                            err_text = detail.get("error") or detail.get("message") or ""
                            if isinstance(err_text, str) and err_text.strip():
                                structured.append(f"{test_name}: {err_text.strip()[:300]}")
                            if len(structured) >= 3:
                                break
                        if len(structured) >= 3:
                            break
                if structured:
                    err_details = f"{err_details} | " + "; ".join(structured)
            elif raw_output:
                # Pega as últimas 800 letras do stdout/stderr (onde fica a mensagem de erro do compilador)
                err_details = raw_output[-800:].replace("\n", " ").strip()
            else:
                err_details = "Falha de compilação ou execução de testes."

            harness_cmd = harness_result.get("command") or "(comando não detectado)"
            msg = f"FALHA NO QA (Tentativa {qa_attempt}): {failed_cnt} teste(s)/compilação falharam. Detalhes técnicos do erro:\n{err_details}\nComando do harness: {harness_cmd}"
        if criteria_coverage_feedback:
            msg = f"{msg}\n{criteria_coverage_feedback}"
        if contract_tests_feedback:
            msg = f"{msg}\n{contract_tests_feedback}"
        new_feedback = feedback_history + [{"from": "qa", "message": msg, "timestamp": now_iso}]

    # Modo incremental: relatório scoped do slice (slice_failed/regression_failed)
    # + status do slice para o should_retry decidir avanço/retry/auditoria.
    slice_payload_out: dict = {}
    if incremental:
        slice_failed, regression_failed = _classify_slice_failures(harness_result, slice_index)
        slice_id = (current_story or {}).get("id", "US000")
        slice_test_report = {
            **report,
            "slice_id": slice_id,
            "slice_failed": slice_failed,
            "regression_failed": regression_failed,
            "test_scope": "slice",
        }
        slice_status_out = "passed" if is_pass else "failed"
        if slices and 0 <= slice_index < len(slices):
            slices[slice_index]["status"] = slice_status_out
            slices[slice_index]["test_report"] = slice_test_report
        slice_payload_out = {
            "slice_test_report": slice_test_report,
            "slice_status": slice_status_out,
            "slices": slices,
            "test_scope": "slice",
        }

    fingerprints = list(state.get("retry_fingerprints", []) or [])
    doom_detected = False
    doom_reason = None
    if not is_pass:
        fp = compute_qa_fingerprint(code, report)
        fingerprints.append(fp)
        if len(fingerprints) >= 2 and fingerprints[-1] == fingerprints[-2]:
            doom_detected = True
            doom_reason = (
                "Doom-Loop detectado: 2 tentativas consecutivas produziram o mesmo erro sem alteração no código."
            )
            print(f"--- AVISO: {doom_reason} ---")

    return {
        **state,
        "test_report": report,
        "qa_attempt_count": qa_attempt,
        "feedback_history": new_feedback,
        "next_agent": next_agent,
        "retry_fingerprints": fingerprints,
        "doom_loop_detected": doom_detected or bool(state.get("doom_loop_detected")),
        "doom_loop_reason": doom_reason or state.get("doom_loop_reason"),
        **slice_payload_out,
    }


def _slice_fail_payload(slices: list, slice_index: int, current_story: dict | None, report: dict) -> dict:
    """Payload de falha do slice para o caminho 'nenhum código gerado' (QA)."""
    slice_id = (current_story or {}).get("id", "US000")
    slice_test_report = {
        **report,
        "slice_id": slice_id,
        "slice_failed": 1,
        "regression_failed": 0,
        "test_scope": "slice",
    }
    if slices and 0 <= slice_index < len(slices):
        slices[slice_index]["status"] = "failed"
        slices[slice_index]["test_report"] = slice_test_report
    return {
        "slice_test_report": slice_test_report,
        "slice_status": "failed",
        "slices": slices,
        "test_scope": "slice",
    }


def _classify_slice_failures(harness_result: dict, slice_index: int) -> tuple[int, int]:
    """(slice_failed, regression_failed) — separa falhas do slice corrente de regressão.

    Uma falha pertence ao SLICE quando o caminho do teste começa com
    ``tests/slices/slice_{NN}/`` (contrato do slice corrente, gravado pelo
    Test Writer); qualquer outro caminho (tests/ da raiz, slices anteriores,
    fontes) é REGRESSÃO. Erros livres sem caminho contam como falha do slice
    (conservador: não provam regressão).
    """
    prefix = f"tests/slices/slice_{int(slice_index):02d}/"
    slice_failed = 0
    regression_failed = 0

    suites = harness_result.get("results_by_suite") or []
    for suite in suites:
        if not isinstance(suite, dict):
            continue
        for detail in suite.get("failed_tests_details") or []:
            if not isinstance(detail, dict):
                continue
            name = str(detail.get("test_name") or detail.get("name") or "")
            if not name:
                continue
            if name.startswith(prefix):
                slice_failed += 1
            else:
                regression_failed += 1

    free_errors = [e for e in (harness_result.get("errors") or []) if isinstance(e, str) and e.strip()]
    slice_failed += len(free_errors)
    return slice_failed, regression_failed


def _run_harness(project_dir: str, stack: str = "", output_dir: str = ".") -> dict:
    """Executa testes utilizando o TestHarnessRunner unificado do LoopForge."""
    from dataclasses import asdict

    from ...runner.harness.runner import TestHarnessRunner

    # Prefere o dir da run (output_dir) — o project_dir (".") sempre existe e
    # fazia o harness coletar testes do repo real em vez dos do produto.
    target_dir = output_dir if (output_dir and os.path.exists(output_dir)) else project_dir

    # Self-healing Go apenas quando a stack DECIDIDA é Go (evita rodar
    # 'go mod tidy' por causa de go.mod obsoleto de uma run anterior).
    if "go" in stack.lower() and os.path.exists(os.path.join(target_dir, "go.mod")) and shutil.which("go"):
        with suppress(Exception):
            subprocess.run("go mod tidy", shell=True, cwd=target_dir, capture_output=True, timeout=60)

    runner = TestHarnessRunner(stack=stack, auto_format=True)
    # Executa auto-formatação da stack (ruff format, cargo fmt, gofmt, prettier)
    if hasattr(runner, "run_auto_formatter"):
        runner.run_auto_formatter(target_dir)
    format_issues = runner.run_format_check(target_dir)
    res = runner.run(target_dir)
    result = cast("dict", asdict(res)) if hasattr(res, "__dataclass_fields__") else cast("dict", res)
    if format_issues:
        result["format_issues"] = format_issues
    return result


def _find_contract_test_files(product_dir: str, stack: str) -> list[Path]:
    """Descobre arquivos de teste do contrato conforme a stack decidida.

    Antes só reconhecia `test_*.py`/`*_test.py` em tests/ → stack java/rust/go
    com contract_tests dava falso FAIL "contrato não encontrado". Padrões por
    stack seguem o TechStackRegistry (pytest, junit/maven, cargotest, gotest,
    vitest/npm). Stack desconhecida/vazia mantém o comportamento original.
    """
    root = Path(product_dir)
    stack_lower = (stack or "").lower().strip()

    if any(m in stack_lower for m in ("java", "spring", "maven", "gradle")):
        patterns = ["src/test/**/*.java"]
    elif any(m in stack_lower for m in ("rust", "cargo", "actix")):
        patterns = ["tests/**/*.rs", "src/**/*_test.rs", "**/*_test.rs"]
    elif any(m in stack_lower for m in ("go", "golang", "gin")):
        patterns = ["**/*_test.go"]
    elif any(m in stack_lower for m in ("javascript", "typescript", "node", "express", "react", "next", "js", "ts")):
        patterns = [
            "**/*.test.js",
            "**/*.test.ts",
            "**/*.test.jsx",
            "**/*.test.tsx",
            "**/*.spec.js",
            "**/*.spec.ts",
            "**/*.spec.jsx",
            "**/*.spec.tsx",
        ]
    else:
        # python ou stack desconhecida: testes-contrato na raiz de tests/ E
        # recursivos (tests/slices/slice_NN/ no modo incremental).
        patterns = ["tests/test_*.py", "tests/*_test.py", "tests/**/test_*.py", "tests/**/*_test.py"]

    files: list[Path] = []
    for pattern in patterns:
        files.extend(root.glob(pattern))
    return files


def _build_report_from_harness(
    report_id: str,
    timestamp: str,
    harness_result: dict,
    user_story_id: str = "US001",
) -> dict:
    """Constrói relatório de teste estruturado e preciso a partir da execução direta do harness."""
    errors = list(harness_result.get("errors", []))
    total = harness_result.get("total", 0)
    passed = harness_result.get("passed", 0)
    duration_s = harness_result.get("duration_ms", 0) / 1000.0
    command_used = harness_result.get("command", "")

    no_tests_found = False
    if total == 0:
        if not errors:
            if harness_result.get("command_missing"):
                # Comando de teste não encontrado no PATH: não é "nenhum teste
                # coletado", é harness ausente (ex.: pytest fora do venv).
                errors.append(
                    "Harness: comando de teste não encontrado no PATH (pytest). Verifique a instalação do venv."
                )
            else:
                # Nenhum teste coletado pelo harness sem erros reais de execução:
                # sinaliza explicitamente para o developer ajustar tests/ da stack.
                no_tests_found = True
                command_display = command_used or "(comando não detectado)"
                errors.append(
                    f"Nenhum teste foi coletado pelo harness (comando {command_display}). "
                    "Verifique se tests/ existe, importa corretamente e contém testes da stack decidida."
                )
        else:
            errors.append("Nenhum teste foi executado ou nenhum harness/compilador foi encontrado.")
        failed = len(errors)
        status = "FAIL"
    else:
        failed = len(errors)
        status = "PASS" if failed == 0 and passed > 0 else "FAIL"

    report: dict[str, Any] = {
        "id": report_id,
        "user_story_id": user_story_id,
        "commit_hash": "local_head",
        "execution_timestamp": timestamp,
        "executed_by": "qa.agent",
        "environment": {"name": "local", "config_hash": None},
        "summary": {
            "status": status,
            "total_tests": max(total, passed + failed),
            "tests_passed": passed,
            "tests_failed": failed,
            "tests_skipped": 0,
            "flaky_tests_detected": 0,
            "duration_seconds": duration_s,
        },
        "results_by_suite": [
            {
                "suite_name": "harness",
                "suite_type": "unit/integration",
                "status": status,
                "duration_seconds": duration_s,
                "total_tests": max(total, passed + failed),
                "failed_tests_details": [{"error": err} for err in errors],
            }
        ],
        "code_coverage": None,
        "artifacts": None,
    }
    if no_tests_found:
        report["summary"]["no_tests_found"] = True
    return report


def _attempt_dependency_self_healing(project_dir: str, harness_result: dict) -> bool:
    """Tenta auto-corrigir erros de incompatibilidade de versão de dependências (Cargo.toml e package.json)."""
    import re
    import subprocess

    errors_str = " ".join(str(e) for e in harness_result.get("errors", []))
    output_str = str(harness_result.get("output", "")) + " " + errors_str

    cargo_toml = Path(project_dir) / "Cargo.toml"
    if cargo_toml.exists():
        # Cenário 1: "cargo update <crate> --precise ver"
        m = re.search(r"cargo update\s+([a-zA-Z0-9_-]+)(?:@\S+)?\s+--precise\s+(\S+)", output_str)
        if m:
            crate_name, target_ver = m.group(1), m.group(2)
            print(f"--- INFO: Self-Healing Cargo: executando cargo update -p {crate_name} --precise {target_ver} ---")
            try:
                subprocess.run(
                    f"cargo update -p {crate_name} --precise {target_ver}",
                    shell=True,
                    cwd=project_dir,
                    capture_output=True,
                    timeout=30,
                )
                return True
            except Exception:
                pass

        # Cenário 2: "requires rustc X" ou "feature `edition2024` is required"
        if "requires rustc" in output_str.lower() or "edition2024" in output_str.lower():
            print("--- INFO: Self-Healing Cargo: ajustando edição para 2021 em Cargo.toml ---")
            try:
                content = cargo_toml.read_text(encoding="utf-8")
                updated = re.sub(r'edition\s*=\s*"2024"', 'edition = "2021"', content)
                if updated != content:
                    cargo_toml.write_text(updated, encoding="utf-8")
                    return True
            except Exception:
                pass

    package_json = Path(project_dir) / "package.json"
    if package_json.exists() and ("peer dependency" in output_str.lower() or "eresolve" in output_str.lower()):
        print("--- INFO: Self-Healing NPM: executando npm install com --legacy-peer-deps ---")
        try:
            subprocess.run(
                "npm install --legacy-peer-deps", shell=True, cwd=project_dir, capture_output=True, timeout=30
            )
            return True
        except Exception:
            pass

    # Onda 2 (2.4): Python (pip) — requirements.txt/pyproject.toml presente e erro
    # de import/instalação → instala o pacote faltante (extraído do ModuleNotFoundError)
    # ou o requirements.txt inteiro. Usa o python do venv do projeto quando existir.
    pip_error = (
        "modulenotfounderror" in output_str.lower()
        or "no matching distribution" in output_str.lower()
        or "could not find a version" in output_str.lower()
    )
    pip_manifest = Path(project_dir) / "requirements.txt"
    if pip_error and (pip_manifest.exists() or (Path(project_dir) / "pyproject.toml").exists()):
        missing_pkg = None
        m = re.search(r"No module named ['\"]?(\w+)", output_str)
        if m:
            missing_pkg = m.group(1)
        try:
            venv_python = Path(project_dir) / ".venv" / "bin" / "python"
            python_bin = str(venv_python) if venv_python.exists() else "python"
            if missing_pkg:
                pip_cmd = f"{python_bin} -m pip install {missing_pkg}"
            elif pip_manifest.exists():
                pip_cmd = f"{python_bin} -m pip install -r {pip_manifest}"
            else:
                pip_cmd = f"{python_bin} -m pip install -e ."
            print(f"--- INFO: Self-Healing pip: {pip_cmd} ---")
            res = subprocess.run(pip_cmd, shell=True, cwd=project_dir, capture_output=True, timeout=60)
            if res.returncode == 0:
                return True
        except Exception:
            pass

    # Onda 2 (2.4): Java/Maven — pom.xml presente e falha de resolução de
    # dependências → mvn dependency:resolve (se mvn no PATH) baixa as deps.
    maven_error = "could not resolve dependencies" in output_str.lower() or "build failure" in output_str.lower()
    if (Path(project_dir) / "pom.xml").exists() and maven_error and shutil.which("mvn"):
        print("--- INFO: Self-Healing Maven: executando mvn dependency:resolve -q ---")
        try:
            res = subprocess.run(
                "mvn dependency:resolve -q", shell=True, cwd=project_dir, capture_output=True, timeout=120
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass

    go_mod = Path(project_dir) / "go.mod"
    if go_mod.exists() or "no required module" in output_str.lower() or "cannot find module" in output_str.lower():
        print("--- INFO: Self-Healing Go: executando go mod tidy ---")
        try:
            subprocess.run("go mod tidy", shell=True, cwd=project_dir, capture_output=True, timeout=60)
            return True
        except Exception:
            pass

    return False


def _mock_report(report_id: str, timestamp: str) -> dict:
    return {
        "id": report_id,
        "user_story_id": "US001",
        "commit_hash": "mock_commit_hash",
        "execution_timestamp": timestamp,
        "executed_by": "qa.agent",
        "environment": {"name": "local", "config_hash": None},
        "summary": {
            "status": "PASS",
            "total_tests": 10,
            "tests_passed": 10,
            "tests_failed": 0,
            "tests_skipped": 0,
            "flaky_tests_detected": 0,
            "duration_seconds": 1.5,
        },
        "results_by_suite": [
            {
                "suite_name": "unit",
                "suite_type": "unit",
                "status": "PASS",
                "duration_seconds": 1.0,
                "total_tests": 8,
                "failed_tests_details": [],
            },
            {
                "suite_name": "integration",
                "suite_type": "integration",
                "status": "PASS",
                "duration_seconds": 0.5,
                "total_tests": 2,
                "failed_tests_details": [],
            },
        ],
        "code_coverage": None,
        "artifacts": None,
    }
