"""
Nó Tech Lead: valida user stories e gera especificação técnica.
Usa template tech_spec_template.md do The Foundry e Pydantic para feedback.
"""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


class ValidationResult(BaseModel):
    """Resultado da validação do Tech Lead sobre as user stories."""
    needs_feedback: bool = Field(..., description="True se user stories precisam de revisão")
    feedback_message: str = Field(..., description="Feedback detalhado para o PM")
    approved_stories: list[str] = Field(default_factory=list, description="IDs das stories aprovadas")


def tech_lead(state: GraphState) -> dict:
    """Valida user stories e gera tech spec."""
    print("---EXECUTANDO NÓ: Tech Lead---")

    # Reutiliza tech spec se já gerada em etapa anterior do plano
    if state.get("tech_spec"):
        print("--- INFO: Tech Lead reutilizando Tech Spec existente no estado ---")
        return {**state, "next_agent": "developer"}

    user_stories = state.get("user_stories", [])
    if not user_stories:
        raise ValueError("User stories não encontradas no estado")


    now_iso = datetime.now(UTC).isoformat()
    now_date = now_iso.split("T")[0]

    # Carrega template tech_spec.md do Foundry se disponível
    template_path = Path(state.get("ontology_path", "examples/the-foundry")) / \
                    "company_context/shared_knowledge/artifact_templates/tech_spec_template.md"
    if template_path.exists():
        tech_spec_template = template_path.read_text(encoding="utf-8")
    else:
        tech_spec_template = "# Especificação Técnica: {title}\n\n## Visão Geral\n{description}\n\n## Arquitetura\n{architecture}\n\n## Stack\n{stack}\n\n## User Stories\n{user_stories}\n\n## Decisões\n{decisions}"

    if state.get("mock_llm"):
        print("--- INFO: Tech Lead modo MOCK ---")
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date)
        return {**state, "tech_spec": tech_spec, "next_agent": "developer"}

    print("--- INFO: Tech Lead usando OpenCode via subprocesso ---")

    stories_str = "\n".join(
        f"{us.get('id', 'N/A')}: {us.get('title', '')} — {us.get('as_a', '')} quer {us.get('i_want_to', '')} para {us.get('so_that', '')}"
        for us in user_stories
    )

    # Fase 1: Validar user stories
    try:
        validation = call_llm_via_opencode(
            system_prompt="""Você é um Tech Lead. Revise as user stories abaixo.

Critérios de análise:
- As histórias são claras e sem ambiguidade?
- Os critérios de aceitação são testáveis?
- Há informações técnicas faltando?

Responda com:
- needs_feedback: true se alguma história precisa de revisão
- feedback_message: feedback detalhado
- approved_stories: IDs das histórias aprovadas""",
            user_prompt=f"User Stories:\n{stories_str}",
            schema_model=ValidationResult,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )

        if validation.get("needs_feedback"):
            feedback_msg = validation.get('feedback_message', '')
            print(f"--- AVISO: Tech Lead solicita feedback: ---")
            print(f"--- {feedback_msg[:500]} ---")
            if len(feedback_msg) > 500:
                print("--- (Feedback truncado em 500 caracteres) ---")
            state["feedback_history"] = state.get("feedback_history", []) + [
                {"from": "tech_lead", "message": validation.get("feedback_message", ""), "timestamp": now_iso}
            ]
    except Exception as e:
        print(f"--- ERRO TL validação: {e} ---")

    # Fase 2: Gerar tech spec
    print("--- Gerando especificação técnica ---")

    try:
        # Trunca template e stories para caber no contexto do modelo gratuito
        truncated_template = tech_spec_template[:1500]
        truncated_stories = "\n".join(
            f"{us.get('id', '')}: {us.get('title', '')}" for us in user_stories[:5]
        )
        tech_spec = call_llm_via_opencode(
            system_prompt=f"""Você é um Tech Lead. Crie uma especificação técnica.

Stack do projeto: {state.get('stack', 'N/A')}

Template (use como guia):
{truncated_template}""",
            user_prompt=f"User Stories (apenas títulos):\n{truncated_stories}",
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )
    except Exception as e:
        print(f"--- ERRO TL tech spec: {e} ---")
        tech_spec = _mock_tech_spec(user_stories, tech_spec_template, now_date)

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        epic_id = user_stories[0].get("epic_id", "UNKNOWN")
        path = os.path.join(output_dir, f"tech_spec_{epic_id}.md")
        with open(path, "w") as f:
            f.write(tech_spec)
        print(f"--- INFO: Tech spec salva em {path} ---")

    return {**state, "tech_spec": tech_spec, "next_agent": "developer"}


def _mock_tech_spec(user_stories: list[dict], template: str, date: str) -> str:
    epic_id = user_stories[0].get("epic_id", "UNKNOWN") if user_stories else "UNKNOWN"
    stories_list = "\n".join(f"- {us.get('id', '')}: {us.get('title', '')}" for us in user_stories)

    return template.format(
        title=f"Especificação Técnica para Épico {epic_id}",
        description="Descrição técnica",
        architecture="Arquitetura a ser definida",
        stack="Stack do projeto",
        user_stories=stories_list,
        decisions="Decisões arquiteturais",
    ) if "{title}" in template else f"""# Especificação Técnica - {epic_id}

**Data:** {date}
**Status:** Draft

## User Stories
{stories_list}

## Stack
- Linguagem: Python
- Framework: FastAPI
- Banco: PostgreSQL

## Decisões
- API REST com validação Pydantic
"""
