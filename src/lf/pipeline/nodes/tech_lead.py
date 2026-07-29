"""
Nó Tech Lead: valida user stories, decide a melhor stack tecnológica e gera especificação técnica.
Usa template tech_spec_template.md do The Foundry e Pydantic para feedback.
"""
from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


class ValidationResult(BaseModel):
    """Resultado da validação do Tech Lead sobre as user stories."""
    needs_feedback: bool = Field(..., description="True se user stories precisam de revisão")
    feedback_message: str = Field(..., description="Feedback detalhado para o PM")
    approved_stories: list[str] = Field(default_factory=list, description="IDs das histórias aprovadas")
    recommended_stack: str = Field("python", description="Stack recomendada (ex: python, rust, java, javascript, go)")


def _extract_stack_from_text(text: str) -> str:
    """Extrai a linguagem/stack principal recomendada no texto da tech spec."""
    text_lower = text.lower()
    for lang in ("rust", "python", "java", "javascript", "typescript", "go", "csharp", "ruby", "php"):
        if lang in text_lower:
            return lang
    return "python"


def tech_lead(state: GraphState) -> dict:
    """Valida user stories, decide a stack do projeto e gera tech spec."""
    print("---EXECUTANDO NÓ: Tech Lead---")

    user_stories = state.get("user_stories", [])
    idea = state.get("idea", "")
    current_stack = state.get("stack")  # Se informado pelo usuário via CLI override

    # Reutiliza tech spec se já gerada em etapa anterior do plano
    if state.get("tech_spec"):
        print("--- INFO: Tech Lead reutilizando Tech Spec existente no estado ---")
        decided_stack = current_stack or _extract_stack_from_text(state["tech_spec"])
        return {**state, "stack": decided_stack, "next_agent": "developer"}

    now_iso = datetime.now(UTC).isoformat()
    now_date = now_iso.split("T")[0]

    # Carrega template tech_spec.md do Foundry se disponível
    template_path = Path(state.get("ontology_path", "examples/the-foundry")) / \
                    "company_context/shared_knowledge/artifact_templates/tech_spec_template.md"
    if template_path.exists():
        tech_spec_template = template_path.read_text(encoding="utf-8")
    else:
        tech_spec_template = "# Especificação Técnica: {title}\n\n## Visão Geral\n{description}\n\n## Arquitetura\n{architecture}\n\n## Stack Recomendada\n{stack}\n\n## User Stories\n{user_stories}\n\n## Decisões\n{decisions}"

    if state.get("mock_llm"):
        print("--- INFO: Tech Lead modo MOCK ---")
        decided_stack = current_stack or _extract_stack_from_text(idea) or "python"
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date, decided_stack)
        return {**state, "stack": decided_stack, "tech_spec": tech_spec, "next_agent": "developer"}

    print("--- INFO: Tech Lead analisando problema e decidindo stack ---")

    stories_str = "\n".join(
        f"{us.get('id', 'N/A')}: {us.get('title', '')} — {us.get('as_a', '')} quer {us.get('i_want_to', '')} para {us.get('so_that', '')}"
        for us in user_stories
    )

    # Fase 1: Validar user stories e recomendar stack
    decided_stack = current_stack
    new_feedback = list(state.get("feedback_history", []))

    try:
        validation = call_llm_via_opencode(
            system_prompt="""Você é um Tech Lead. Revise as user stories e recomende a melhor stack.

Analise o problema e recomende a melhor stack (linguagem + framework + ferramentas). Considere:
- Tipo de projeto e escopo
- Performance e segurança necessárias
- Ecossistema e produtividade

Responda com:
- needs_feedback: true se alguma história precisa de revisão
- feedback_message: feedback detalhado
- approved_stories: IDs das histórias aprovadas
- recommended_stack: linguagem ou stack recomendada (ex: python, rust, java, javascript, go)""",
            user_prompt=f"Ideia do Projeto: {idea}\n\nUser Stories:\n{stories_str}",
            schema_model=ValidationResult,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )

        if not decided_stack:
            decided_stack = validation.get("recommended_stack", "python")

        if validation.get("needs_feedback"):
            feedback_msg = validation.get('feedback_message', '')
            print(f"--- AVISO: Tech Lead solicita feedback: ---")
            print(f"--- {feedback_msg[:500]} ---")
            new_feedback.append(
                {"from": "tech_lead", "message": feedback_msg, "timestamp": now_iso}
            )
    except Exception as e:
        print(f"--- ERRO TL validação: {e} ---")
        if not decided_stack:
            decided_stack = _extract_stack_from_text(idea) or "python"

    # Fase 2: Gerar tech spec
    print(f"--- Gerando especificação técnica (Stack decidida pelo TL: {decided_stack}) ---")

    try:
        truncated_template = tech_spec_template[:1500]
        truncated_stories = "\n".join(
            f"{us.get('id', '')}: {us.get('title', '')}" for us in user_stories[:5]
        )
        tech_spec = call_llm_via_opencode(
            system_prompt=f"""Você é um Tech Lead. Crie uma especificação técnica detalhada.

Stack decidida pelo Tech Lead: {decided_stack}

Template (use como guia):
{truncated_template}""",
            user_prompt=f"Ideia: {idea}\nUser Stories:\n{truncated_stories}",
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )
    except Exception as e:
        print(f"--- ERRO TL tech spec: {e} ---")
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date, decided_stack)

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        epic_id = user_stories[0].get("epic_id", "UNKNOWN") if user_stories else "UNKNOWN"
        path = os.path.join(output_dir, f"tech_spec_{epic_id}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(tech_spec)
        print(f"--- INFO: Tech spec salva em {path} ---")

    return {
        **state,
        "stack": decided_stack,
        "tech_spec": tech_spec,
        "feedback_history": new_feedback,
        "next_agent": "developer",
    }


def _mock_tech_spec(user_stories: list[dict], template: str, date: str, stack: str = "python") -> str:
    epic_id = user_stories[0].get("epic_id", "UNKNOWN") if user_stories else "UNKNOWN"
    stories_list = "\n".join(f"- {us.get('id', '')}: {us.get('title', '')}" for us in user_stories)

    return template.format(
        title=f"Especificação Técnica para Épico {epic_id}",
        description="Descrição técnica",
        architecture="Arquitetura a ser definida",
        stack=f"Stack decidida pelo Tech Lead: {stack}",
        user_stories=stories_list,
        decisions="Decisões arquiteturais",
    ) if "{title}" in template else f"""# Especificação Técnica - {epic_id}

**Data:** {date}
**Status:** Approved

## User Stories
{stories_list}

## Stack Decidida pelo Tech Lead
- Linguagem/Framework: {stack}

## Decisões
- Implementar projeto multi-arquivo completo com testes automatizados.
"""
