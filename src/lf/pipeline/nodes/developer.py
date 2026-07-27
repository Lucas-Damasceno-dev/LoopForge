#-*- coding: utf-8 -*-
"""
Nó Developer: recebe tech spec e gera código REAL via OpenCode.
Usa subprocesso para invocar OpenCode com contexto completo.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import time
from typing import Optional

from ...runner.opencode import OpenCodeRunner, OpenCodeResult, detect_changed_files
from ...pipeline.state import GraphState


def _extract_generated_code(
    result: OpenCodeResult,
    project_dir: str,
    start_time: float,
) -> str:
    """Extrai o código fonte real dos arquivos criados/modificados pelo OpenCode.
    Se nenhum arquivo foi alterado no disco, tenta extrair blocos de código do stdout,
    ou como fallback retorna o stdout."""
    changed_files = result.changed_files or detect_changed_files(project_dir, start_time)

    ignored_names = {
        "generated_code.py", ".loopforge.json", "llm_cache.sqlite",
        ".users.json", "loop.lock", "package-lock.json", "poetry.lock"
    }
    code_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
        ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sh", ".sql"
    }

    code_files: list[Path] = []
    for fpath_str in changed_files:
        fpath = Path(fpath_str).resolve()
        if fpath.name in ignored_names or fpath.name.startswith("test_report_"):
            continue
        if fpath.suffix.lower() in code_extensions:
            code_files.append(fpath)

    if code_files:
        code_snippets = []
        proj_path = Path(project_dir).resolve()
        for fpath in code_files:
            try:
                try:
                    rel_path = fpath.relative_to(proj_path)
                except ValueError:
                    rel_path = fpath.name
                content = fpath.read_text(encoding="utf-8", errors="replace")
                if len(code_files) == 1:
                    return content
                code_snippets.append(f"# --- File: {rel_path} ---\n{content}")
            except Exception as e:
                print(f"--- AVISO: Falha ao ler arquivo gerado {fpath}: {e} ---")

        if code_snippets:
            return "\n\n".join(code_snippets)

    # Fallback 1: Bloco de código markdown no stdout
    if result.stdout:
        code_match = re.search(
            r"```(?:python|py|javascript|js|typescript|ts)?\s*\n(.*?)\n```",
            result.stdout,
            re.DOTALL,
        )
        if code_match:
            return code_match.group(1).strip()

    # Fallback 2: Stdout bruto
    return result.stdout if result.success else ""


def developer(state: GraphState) -> dict:
    """Recebe tech spec e gera código via OpenCode."""
    print("---EXECUTANDO NÓ: Developer---")

    tech_spec = state.get("tech_spec")
    if not tech_spec:
        raise ValueError("Especificação técnica não encontrada no estado")

    # Mock mode
    if state.get("mock_llm"):
        print("--- INFO: Developer modo MOCK ---")
        mock_code = "# Mock generated code\nprint('Hello from mock developer')"
        return {
            **state,
            "code": mock_code,
            "next_agent": "qa",
            "error": None,
        }

    user_stories = state.get("user_stories", [])
    project_dir = state.get("project_dir", os.getcwd())

    # Monta prompt focado na primeira user story apenas
    stack = state.get("stack", "")
    first_story = user_stories[0] if user_stories else {}
    story_line = f"{first_story.get('id', '')}: {first_story.get('title', '')}" if first_story else "Implementar"

    feedback = state.get("feedback_history", [])
    feedback_context = ""
    if feedback:
        fb = feedback[-1]
        feedback_context = f"\nFeedback da iteração anterior ({fb.get('from', '')}): {fb.get('message', '')[:200]}\n"

    first_story_desc = first_story.get('description', '')[:200]
    prompt = f"""Write a single Python file implementing: {story_line}

Context: {first_story_desc}

REGRAS:
1. Output ONLY valid Python code (no markdown, no explanations)
2. Single file implementation (<200 lines)
3. Must have a main() function
4. Use argparse or click for CLI if applicable"""

    runner = OpenCodeRunner(timeout_seconds=600)
    start_time = time.time()

    print("--- Spawnando OpenCode... ---")
    result = runner.run(
        prompt=prompt,
        project_root=project_dir,
        model="opencode/deepseek-v4-flash-free",
    )

    # Extrai o código fonte real dos arquivos criados/modificados ou stdout
    generated_code = _extract_generated_code(result, project_dir, start_time)
    code_path = os.path.join(state.get("output_dir", "."), "generated_code.py")

    if result.success and generated_code:
        os.makedirs(state.get("output_dir", "."), exist_ok=True)
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(generated_code)
        print(f"--- INFO: Código salvo em {code_path} ---")

    err_msg = result.error
    if not result.success:
        print(f"--- AVISO: OpenCode falhou: {err_msg} ---")
        state["feedback_history"] = state.get("feedback_history", []) + [
            {"from": "developer", "message": f"OpenCode falhou: {err_msg}", "attempt": state.get("attempt_count", 0)}
        ]

    return {
        **state,
        "code": generated_code,
        "next_agent": "qa",
        "error": err_msg,
    }

