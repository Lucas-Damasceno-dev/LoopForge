#-*- coding: utf-8 -*-
"""
Nó Developer: recebe tech spec e gera código REAL via OpenCode.
Usa subprocesso para invocar OpenCode com contexto completo.
"""
from __future__ import annotations
import json
import os
import re
from typing import Optional

from ...runner.opencode import OpenCodeRunner
from ...pipeline.state import GraphState


def developer(state: GraphState) -> dict:
    """Recebe tech spec e gera código via OpenCode."""
    print("---EXECUTANDO NÓ: Developer---")

    tech_spec = state.get("tech_spec")
    if not tech_spec:
        raise ValueError("Especificação técnica não encontrada no estado")

    user_stories = state.get("user_stories", [])
    project_dir = state.get("project_dir", os.getcwd())

    # Monta prompt rico com contexto completo
    stack = state.get("stack", "")
    stories_summary = "\n".join(
        f"- {us.get('id', '')}: {us.get('title', '')} [{us.get('priority', 'Medium')}]"
        for us in user_stories
    ) if user_stories else "N/A"

    feedback = state.get("feedback_history", [])
    feedback_context = ""
    if feedback:
        fb = feedback[-1]
        feedback_context = f"\nFeedback da iteração anterior ({fb.get('from', '')}): {fb.get('message', '')}\n"

    prompt = f"""Você é um Engenheiro de Software Sênior.

OBJETIVO: Implementar o código descrito na especificação técnica abaixo.

STACK: {stack}

USER STORIES A IMPLEMENTAR:
{stories_summary}

{feedback_context}
ESPECIFICAÇÃO TÉCNICA:
{tech_spec[:8000]}

REGRAS:
1. Implemente APENAS o que está na especificação técnica
2. Siga as melhores práticas da stack informada
3. Adicione comentários explicativos onde necessário
4. Estrutura limpa, modular, testável
5. Se for projeto web: inclua package.json/requirements.ts, componentes, rotas
6. Se houver testes no projeto: execute-os e corrija falhas

Ao final, execute: npm test || pytest || cargo test (conforme a stack)
e garanta que os testes passem."""

    runner = OpenCodeRunner(
        prompt=prompt,
        cwd=project_dir,
        timeout_ms=600_000,
        mock=state.get("mock_llm", False),
    )

    print("--- Spawnando OpenCode... ---")
    result = runner.run()

    # Extrai código gerado do stdout
    generated_code = result.stdout if result.success else ""
    code_path = os.path.join(state.get("output_dir", "."), "generated_code.py")

    if result.success and generated_code:
        os.makedirs(state.get("output_dir", "."), exist_ok=True)
        with open(code_path, "w") as f:
            f.write(generated_code)
        print(f"--- INFO: Código salvo em {code_path} ---")

    if not result.success:
        print(f"--- AVISO: OpenCode falhou: {result.error} ---")
        state["feedback_history"] = state.get("feedback_history", []) + [
            {"from": "developer", "message": f"OpenCode falhou: {result.error}", "attempt": state.get("attempt_count", 0)}
        ]

    return {
        **state,
        "code": generated_code,
        "next_agent": "qa",
        "error": result.error,
    }
