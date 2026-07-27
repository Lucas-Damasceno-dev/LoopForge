#-*- coding: utf-8 -*-
"""
Nó Tech Lead: valida user stories e gera especificação técnica.
Usa template tech_spec_template.md do The Foundry e Pydantic para feedback.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from ..llm_factory import get_llm_client
from ...pipeline.state import GraphState


class ValidationResult(BaseModel):
    """Resultado da validação do Tech Lead sobre as user stories."""
    needs_feedback: bool = Field(..., description="True se user stories precisam de revisão")
    feedback_message: str = Field(..., description="Feedback detalhado para o PM")
    approved_stories: list[str] = Field(default_factory=list, description="IDs das stories aprovadas")


def tech_lead(state: GraphState) -> dict:
    """Valida user stories e gera tech spec."""
    print("---EXECUTANDO NÓ: Tech Lead---")

    user_stories = state.get("user_stories", [])
    if not user_stories:
        raise ValueError("User stories não encontradas no estado")

    now_iso = datetime.now(timezone.utc).isoformat()
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

    llm = get_llm_client(
        state["llm_provider"],
        state["llm_model_name"],
        temperature=state.get("llm_temperature", 0.2),
    )
    llm_validation = llm.with_structured_output(ValidationResult)
    print(f"--- INFO: Tech Lead usando {state['llm_provider']}/{state['llm_model_name']} ---")

    stories_str = "\n".join(
        f"{us.get('id', 'N/A')}: {us.get('title', '')} — {us.get('as_a', '')} quer {us.get('i_want_to', '')} para {us.get('so_that', '')}"
        for us in user_stories
    )

    # Fase 1: Validar user stories
    validation_prompt = f"""Você é um Tech Lead. Revise as user stories abaixo.

Critérios de análise:
- As histórias são claras e sem ambiguidade?
- Os critérios de aceitação são testáveis?
- Há informações técnicas faltando?

User Stories:
{stories_str}

Responda com:
- needs_feedback: true se alguma história precisa de revisão
- feedback_message: feedback detalhado
- approved_stories: IDs das histórias aprovadas"""

    try:
        validation = llm_validation.invoke(validation_prompt)

        if validation.needs_feedback:
            print(f"--- AVISO: Tech Lead solicita feedback: {validation.feedback_message[:100]}... ---")
            # Gera tech spec mesmo assim com as histórias aprovadas
            state["feedback_history"] = state.get("feedback_history", []) + [
                {"from": "tech_lead", "message": validation.feedback_message, "timestamp": now_iso}
            ]
    except Exception as e:
        print(f"--- ERRO TL validação: {e} ---")
        validation = ValidationResult(needs_feedback=False, feedback_message="", approved_stories=[us.get("id", "") for us in user_stories])

    # Fase 2: Gerar tech spec
    print("--- Gerando especificação técnica ---")
    tech_spec_prompt = f"""Você é um Tech Lead. Crie uma especificação técnica detalhada.

Stack do projeto: {state.get('stack', 'N/A')}

User Stories:
{stories_str}

Template:
{tech_spec_template}

Preencha todas as seções do template com informações técnicas precisas.
Inclua decisões arquiteturais, padrões, e tradeoffs quando apropriado.
Use o template como guia, não como limite — adicione seções conforme necessário."""

    try:
        llm_plain = get_llm_client(
            state["llm_provider"],
            state["llm_model_name"],
            temperature=state.get("llm_temperature", 0.2),
        )
        response = llm_plain.invoke(tech_spec_prompt)
        tech_spec = response.content if hasattr(response, "content") else str(response)
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
