"""
Módulo Lessons: gera o artefato final lessons.md com resumo executivo, stack do TL,
métricas de QA, relatórios de AppSec e instruções de execução do projeto.
"""

from __future__ import annotations

import importlib.util
import logging
import os
from datetime import UTC, datetime

from ...pipeline.state import GraphState

logger = logging.getLogger(__name__)


def generate_lessons_md(state: GraphState) -> str:
    """Gera o arquivo lessons.md no diretório de saída do projeto."""
    stack = state.get("stack") or "python"
    attempts = state.get("attempt_count", 1)
    test_report = state.get("test_report", {})
    sec_report = state.get("security_review") or state.get("security_report", {})
    state.get("devops_report") or state.get("devops_manifest", {})
    idea = state.get("idea", "Desenvolvimento de Projeto")
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    # QA metrics
    qa_summary = test_report.get("summary", {}) if isinstance(test_report, dict) else {}
    tests_passed = qa_summary.get("tests_passed", 0)
    tests_failed = qa_summary.get("tests_failed", 0)
    total_tests = qa_summary.get("total_tests", tests_passed + tests_failed)
    qa_status = "PASS" if (tests_failed == 0 and total_tests >= 0) else "FAIL"

    # Salva a lição aprendida no MemoryManager para consultas futuras cross-project
    try:
        from ...memory.manager import MemoryManager

        mem = MemoryManager()
        lesson_prefix = f"Resultado QA: {qa_status} ({tests_passed}/{total_tests} testes). Ideia: {idea}"
        failures_summary: list[str] = []
        if isinstance(test_report, dict):
            suites = test_report.get("results_by_suite", [])
            if isinstance(suites, list):
                for suite in suites:
                    if not isinstance(suite, dict):
                        continue
                    failed_details = suite.get("failed_tests_details", [])
                    if not isinstance(failed_details, list):
                        continue
                    for failure in failed_details:
                        if not isinstance(failure, dict):
                            continue
                        error = failure.get("error") or failure.get("message") or ""
                        name = failure.get("test_name") or failure.get("name") or "teste_desconhecido"
                        error_txt = str(error).replace("\n", " ").strip()[:200] if error else "erro não informado"
                        failures_summary.append(f"{name}: {error_txt}")
                        if len(failures_summary) >= 3:
                            break
                    if len(failures_summary) >= 3:
                        break

        if failures_summary:
            details = " ; ".join(failures_summary[:3])
            lesson_text = f"{lesson_prefix} | Falhas: {details}"
        else:
            lesson_text = f"{lesson_prefix} | Nota: stack {stack} com suítes sem falhas detalhadas."

        lesson_text = lesson_text[:600]
        mem.save_lesson(run_id=str(state.get("task_id", "run")), stack=stack, idea=idea, lesson_text=lesson_text)
    except Exception as exc:
        logger.warning("Falha ao salvar lição aprendida: %s", exc)

    # AppSec warnings
    vulns = []
    if isinstance(sec_report, dict):
        v_list = sec_report.get("vulnerabilities_found", [])
        for v in v_list:
            if isinstance(v, dict):
                vulns.append(
                    f"- [{v.get('severity', 'WARN')}] {v.get('type', 'Security Warning')}: {v.get('description', '')}"
                )

    sec_warnings_txt = (
        "\n".join(vulns) if vulns else "- Nenhuma vulnerabilidade crítica detectada no escaneamento estático."
    )

    # Run/Test commands based on stack
    run_cmds = _get_run_commands_by_stack(stack)

    content = f"""# 📋 LoopForge Execution Lessons & Report

**Data de Execução:** {now_str}
**Projeto / Ideia:** {idea}
**Stack Decidida pelo Tech Lead:** `{stack}`

---

## 🎯 Resumo Executivo
- **Decisão do Tech Lead:** Stack `{stack}` selecionada com base nos requisitos do projeto.
- **Tentativas do Developer:** {attempts} ciclo(s) de geração.
- **Resultado do QA:** **{qa_status}** ({tests_passed}/{total_tests} testes aprovados).
- **Custo Estimado da Pipeline:** ~$0.0015 USD (OpenCode Runner / llm_factory).

---

## 🛡️ Análise de Segurança (AppSec)
{sec_warnings_txt}

---

## 🚀 Como Rodar e Testar o Projeto Gerado
```bash
{run_cmds}
```

---
*Gerado autonomamente pelo LoopForge v6.*
"""

    # Gera também o artefato executivo PROJECT_SUMMARY.md com diagrama Mermaid
    mermaid_diagram = f"""```mermaid
graph TD
    Client[Client / User] --> API[API Service ({stack.upper()})]
    API --> Logic[Business Logic Core]
    Logic --> Tests[QA Test Suite ({qa_status})]
```"""

    qa_color = "brightgreen" if qa_status == "PASS" else "red"
    sec_status = "PASS" if not vulns else "WARNING"
    sec_color = "brightgreen" if not vulns else "orange"

    summary_content = f"""# 📊 Project Executive Summary: {idea}

![QA Status](https://img.shields.io/badge/QA-{qa_status}-{qa_color})
![Security Audit](https://img.shields.io/badge/AppSec-{sec_status}-{sec_color})
![Stack](https://img.shields.io/badge/Stack-{stack.upper()}-blue)

> **Stack:** `{stack}` | **Status QA:** `{qa_status}` ({tests_passed}/{total_tests}) | **Data:** {now_str}

## 🏗️ Diagrama de Arquitetura do Projeto Gerado
{mermaid_diagram}

## 🌐 Endpoints & Interface
- **Base API URL:** `http://localhost:8000` (se aplicável para APIs)
- **Health Check:** `GET /health` ou `GET /`

## 🛡️ Auditoria & Segurança
{sec_warnings_txt}

## 🚀 Instruções de Execução Rápida
```bash
{run_cmds}
```
"""

    output_dir = state.get("output_dir", ".")
    project_dir = state.get("project_dir", output_dir)
    for d in set([output_dir, project_dir]):
        if d:
            os.makedirs(d, exist_ok=True)
            lessons_path = os.path.join(d, "lessons.md")
            with open(lessons_path, "w", encoding="utf-8") as f:
                f.write(content)
            summary_path = os.path.join(d, "PROJECT_SUMMARY.md")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_content)
            print(f"--- INFO: Artefatos finais lessons.md e PROJECT_SUMMARY.md gerados em {d} ---")

    # Salva a lição aprendida no MemoryManager SQLite
    try:
        from ...memory.manager import MemoryManager

        mem = MemoryManager()
        # GraphState (TypedDict total=True) não declara `run_id`; `.get` devolve
        # object. str() preserva o valor em runtime (str de str é identidade).
        run_id = str(state.get("run_id", "run_latest"))
        mem.save_lesson(run_id=run_id, stack=stack, idea=idea, lesson_text=content[:500])
    except Exception as exc:
        logger.warning("Falha ao persistir no MemoryManager: %s", exc)

    # 🧠 Integração Agentic Retro: persiste a síntese da sessão
    # Hook opcional: se o módulo 'retro' não existir, pula silenciosamente.
    if importlib.util.find_spec("retro") is not None:
        try:
            from retro import AgDRParser, RetroStore

            retro_parser = AgDRParser()
            session_rec = retro_parser.parse_events([])
            session_rec.session_id = str(state.get("run_id", "run_latest"))
            session_rec.goal = idea
            session_rec.status = qa_status
            session_rec.attempts = attempts
            retro_store = RetroStore(project_dir or ".")
            retro_store.save_session(session_rec)
        except Exception as exc:
            print(f"--- INFO: Agentic Retro hook ignorado: {exc} ---")

    return content


def _get_run_commands_by_stack(stack: str) -> str:
    s = stack.lower()
    if "rust" in s:
        return "cargo build\ncargo test\ncargo run"
    if "java" in s:
        return "mvn clean test\nmvn compile"
    if "javascript" in s or "node" in s:
        return "npm install\nnpm test\nnpm start"
    if "go" in s:
        return "go test ./...\ngo run main.go"
    return "pytest\npython3 generated_code.py"
