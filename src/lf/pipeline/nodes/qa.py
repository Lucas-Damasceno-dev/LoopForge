"""
Nó QA: executa testes reais via harness e gera relatório estruturado,
sem mutação direta de estado e sem reportar PASS falso para 0 testes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


class TestExecutionReport(BaseModel):
    """Schema baseado em test_execution_report_schema.json do The Foundry."""
    id: str = Field(..., description="EXEC-YYYY-MM-DD-HHMMSS-XXX")
    user_story_id: str = Field(..., description="ID da user story testada")
    commit_hash: str = Field("mock_hash", description="Hash do commit testado")
    execution_timestamp: str = Field(..., description="ISO 8601")
    executed_by: str = Field("qa.agent")
    environment: dict = Field(..., description="name + config_hash")
    summary: dict = Field(..., description="status, total_tests, passed, failed")
    results_by_suite: list[dict] = Field(default_factory=list)
    code_coverage: dict | None = None
    artifacts: dict | None = None


def qa(state: GraphState) -> dict:
    """Analisa código gerado, executa testes e gera relatório."""
    print("---EXECUTANDO NÓ: QA---")

    code = state.get("code", "")
    project_dir = state.get("project_dir", os.getcwd())
    now_iso = datetime.now(UTC).isoformat()
    report_id = f"EXEC-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    feedback_history = list(state.get("feedback_history", []))

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
        print(f"--- AVISO: Testes falharam (tentativa {qa_attempt}/{state.get('max_retries', 3)}). Reportando ao Developer. ---")
        return {
            **state,
            "test_report": fail_report,
            "qa_attempt_count": qa_attempt,
            "feedback_history": new_feedback,
            "next_agent": "developer",
        }

    if state.get("mock_llm"):
        print("--- INFO: QA modo MOCK ---")
        report = _mock_report(report_id, now_iso)
        return {**state, "test_report": report, "next_agent": "appsec"}

    # Fase 1: Executar harness real no projeto
    harness_result = _run_harness(project_dir, state.get("stack", ""), output_dir=state.get("output_dir", "."))

    # Fase 2: Gerar relatório estruturado via OpenCode (com fallback resiliente para o harness)
    user_stories = state.get("user_stories", [])
    user_story_id = user_stories[0].get("id", "US001") if user_stories else "US001"

    # 🩹 Self-Healing MVP de Dependências: se falhar por versão incompatível, tenta auto-fixar
    if (harness_result.get("passed", 0) == 0 or harness_result.get("errors")) and _attempt_dependency_self_healing(project_dir, harness_result):
        print("--- INFO: Re-executando Test Harness após Self-Healing de dependências ---")
        harness_result = _run_harness(project_dir, state.get("stack", ""), output_dir=state.get("output_dir", "."))

    print(f"--- INFO: Harness executado (passou={harness_result.get('passed')}, erros={len(harness_result.get('errors', []))}) ---")

    try:
        qa_prompt = f"""Resultados do Harness:
- Passou: {harness_result.get('passed', 0)}/{harness_result.get('total', 0)} testes
- Erros: {harness_result.get('errors', [])[:3]}
- Tempo: {harness_result.get('duration_ms', 0)}ms

Código implementado:
```
{code[:2000]}
```"""
        report = call_llm_via_opencode(
            system_prompt="""Você é um QA Engineer. Analise o código e resultados de teste abaixo e gere um relatório de execução de testes conforme o schema esperado.

O relatório DEVE ter:
- id: EXEC-YYYY-MM-DD-HHMMSS-XXX
- user_story_id: ID da user story principal
- commit_hash: hash do commit
- execution_timestamp: ISO 8601
- executed_by: qa.agent
- environment: {"name": "local", "config_hash": None}
- summary: {"status": "PASS" ou "FAIL", "total_tests": N, "tests_passed": N, "tests_failed": N, "tests_skipped": N, "flaky_tests_detected": 0, "duration_seconds": N}
- results_by_suite: lista de suites com detalhes""",
            user_prompt=qa_prompt,
            schema_model=TestExecutionReport,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )
    except Exception as e:
        print(f"--- ERRO QA (Construindo relatório direto do Harness): {e} ---")
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

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"test_report_{report_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Test report salvo em {path} ---")

    is_pass = report.get("summary", {}).get("status") == "PASS" and report.get("summary", {}).get("tests_failed", 1) == 0
    next_agent = "appsec" if is_pass else "developer"

    qa_attempt = state.get("qa_attempt_count", 0)
    new_feedback = feedback_history
    if not is_pass:
        qa_attempt += 1
        print(f"--- AVISO: Testes falharam (tentativa {qa_attempt}/{state.get('max_retries', 3)}). Reportando ao Developer. ---")
        failed_cnt = report.get("summary", {}).get("tests_failed", 1)

        # Extrai os detalhes reais do erro do compilador/harness
        err_list = harness_result.get("errors", [])
        if err_list:
            err_details = "; ".join(err_list[:3])
        elif raw_output:
            # Pega as últimas 800 letras do stdout/stderr (onde fica a mensagem de erro do compilador)
            err_details = raw_output[-800:].replace("\n", " ").strip()
        else:
            err_details = "Falha de compilação ou execução de testes."

        msg = f"FALHA NO QA (Tentativa {qa_attempt}): {failed_cnt} teste(s)/compilação falharam. Detalhes técnicos do erro:\n{err_details}"
        new_feedback = feedback_history + [{"from": "qa", "message": msg, "timestamp": now_iso}]

    return {
        **state,
        "test_report": report,
        "qa_attempt_count": qa_attempt,
        "feedback_history": new_feedback,
        "next_agent": next_agent,
    }


def _run_harness(project_dir: str, stack: str = "", output_dir: str = ".") -> dict:
    """Executa testes utilizando o TestHarnessRunner unificado do LoopForge."""
    from dataclasses import asdict

    from ...runner.harness.runner import TestHarnessRunner
    target_dir = project_dir if (project_dir and os.path.exists(project_dir)) else output_dir

    if ("go" in stack.lower() or os.path.exists(os.path.join(target_dir, "go.mod"))) and shutil.which("go"):
        with suppress(Exception):
            subprocess.run("go mod tidy", shell=True, cwd=target_dir, capture_output=True, timeout=60)

    runner = TestHarnessRunner(stack=stack)
    res = runner.run(target_dir)
    return asdict(res) if hasattr(res, "__dataclass_fields__") else res


def _exec_cmd(cmd: list[str], cwd: str, name: str, result: dict) -> None:
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        duration = int((time.time() - start) * 1000)
        result["duration_ms"] += duration
        result["total"] += 1

        if proc.returncode == 0:
            result["passed"] += 1
        else:
            stderr = proc.stderr[-500:] if proc.stderr else proc.stdout[-500:]
            result["errors"].append(f"{name}: exit {proc.returncode} — {stderr[:200]}")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        result["total"] += 1
        result["errors"].append(f"{name}: runner indisponível ({e})")


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

    if total == 0:
        errors.append("Nenhum teste foi executado ou nenhum harness/compilador foi encontrado.")
        failed = len(errors)
        status = "FAIL"
    else:
        failed = len(errors)
        status = "PASS" if failed == 0 and passed > 0 else "FAIL"

    return {
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
                subprocess.run(f"cargo update -p {crate_name} --precise {target_ver}", shell=True, cwd=project_dir, capture_output=True, timeout=30)
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
            subprocess.run("npm install --legacy-peer-deps", shell=True, cwd=project_dir, capture_output=True, timeout=30)
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
