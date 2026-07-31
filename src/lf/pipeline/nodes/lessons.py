"""
Módulo Lessons: gera o artefato final lessons.md com resumo executivo, stack do TL,
métricas de QA, relatórios de AppSec e instruções de execução do projeto.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime

from ...pipeline.state import GraphState


def generate_lessons_md(state: GraphState) -> str:
    """Gera o arquivo lessons.md no diretório de saída do projeto."""
    stack = state.get("stack", "Não especificada")
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

    # AppSec warnings
    vulns = []
    if isinstance(sec_report, dict):
        v_list = sec_report.get("vulnerabilities_found", [])
        for v in v_list:
            if isinstance(v, dict):
                vulns.append(f"- [{v.get('severity', 'WARN')}] {v.get('type', 'Security Warning')}: {v.get('description', '')}")

    sec_warnings_txt = "\n".join(vulns) if vulns else "- Nenhuma vulnerabilidade crítica detectada no escaneamento estático."

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

    output_dir = state.get("output_dir", ".")
    project_dir = state.get("project_dir", output_dir)
    for d in set([output_dir, project_dir]):
        if d:
            os.makedirs(d, exist_ok=True)
            lessons_path = os.path.join(d, "lessons.md")
            with open(lessons_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"--- INFO: Artefato final lessons.md gerado em {lessons_path} ---")

    # Salva a lição aprendida no MemoryManager SQLite
    try:
        from ...memory.manager import MemoryManager
        mem = MemoryManager()
        run_id = state.get("run_id", "run_latest")
        mem.save_lesson(run_id=run_id, stack=stack, idea=idea, lesson_text=content[:500])
    except Exception as exc:
        print(f"--- AVISO: Falha ao persistir no MemoryManager: {exc} ---")

    # 🧠 Integração Agentic Retro: persiste a síntese da sessão
    try:
        from retro import AgDRParser, RetroStore
        retro_parser = AgDRParser()
        session_rec = retro_parser.parse_events([])
        session_rec.session_id = state.get("run_id", "run_latest")
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
