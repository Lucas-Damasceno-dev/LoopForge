#-*- coding: utf-8 -*-
"""
Nó Product Manager: quebra épico em user stories estruturadas.
Usa Pydantic structured output com schema do The Foundry.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ..llm_factory import get_llm_client
from ...pipeline.state import GraphState


class UserStorySchema(BaseModel):
    """Schema baseado em user_story_schema.json do The Foundry."""
    id: str = Field(..., description="Identificador E-XXX-USXXX")
    title: str = Field(..., description="Título descritivo")
    epic_id: str = Field(..., description="ID do épico pai")
    as_a: str = Field(..., description="Persona/usuário")
    i_want_to: str = Field(..., description="Funcionalidade desejada")
    so_that: str = Field(..., description="Valor/benefício")
    acceptance_criteria: list[str] = Field(..., description="Critérios de aceitação em Given-When-Then")
    priority: str = Field("Medium", description="Low, Medium, High, Critical")
    status: str = Field("Pending", description="Pending, In Progress, Done, Blocked")
    dates: dict = Field(..., description="created_at")


class UserStoryList(BaseModel):
    """Wrapper para lista de user stories."""
    stories: list[UserStorySchema]


def product_manager(state: GraphState) -> dict:
    """Recebe épico e gera user stories."""
    print("---EXECUTANDO NÓ: Product Manager---")

    epic = state.get("epic")
    if not epic:
        raise ValueError("Épico não encontrado no estado")

    now_iso = datetime.now(timezone.utc).isoformat()

    if state.get("mock_llm"):
        print("--- INFO: PM modo MOCK ---")
        stories = _mock_stories(epic)
        return {**state, "user_stories": stories, "next_agent": "tech_lead"}

    llm = get_llm_client(
        state["llm_provider"],
        state["llm_model_name"],
        temperature=state.get("llm_temperature", 0.3),
    )
    llm_structured = llm.with_structured_output(UserStoryList)
    print(f"--- INFO: PM usando {state['llm_provider']}/{state['llm_model_name']} ---")

    prompt = f"""Você é um Product Manager. Quebre o épico abaixo em user stories detalhadas.

Cada user story DEVE ter TODOS os campos:
- id: {epic.get('id', 'E-001')}-USXXX (sequencial)
- title: descritivo
- epic_id: {epic.get('id', 'E-001')}
- as_a: persona (ex: "motorista de van", "pai de aluno")
- i_want_to: funcionalidade concreta
- so_that: benefício
- acceptance_criteria: lista de strings Given-When-Then
- priority: Medium (padrão)
- status: Pending (padrão)
- dates: {{"created_at": "{now_iso}"}}

Épico:
Título: {epic.get('title', '')}
Descrição: {epic.get('description', '')}
Objetivos: {', '.join(epic.get('business_objectives', []))}
Escopo IN: {', '.join(epic.get('scope_in', []))}
Escopo OUT: {', '.join(epic.get('scope_out', []))}"""

    try:
        result = llm_structured.invoke(prompt)
        stories = []
        for i, us in enumerate(result.stories):
            us_dict = us.model_dump()
            us_dict["id"] = f"{epic.get('id', 'E-001')}-US{i+1:03d}"
            us_dict["epic_id"] = epic.get("id", "E-001")
            us_dict["dates"]["created_at"] = now_iso
            stories.append(us_dict)
    except Exception as e:
        print(f"--- ERRO PM: {e} ---")
        stories = _mock_stories(epic)

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for us in stories:
            path = os.path.join(output_dir, f"us_{us['id']}.json")
            with open(path, "w") as f:
                json.dump(us, f, indent=2, ensure_ascii=False)

    return {**state, "user_stories": stories, "next_agent": "tech_lead"}


def _mock_stories(epic: dict) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return [
        {
            "id": f"{epic.get('id', 'E-001')}-US001",
            "title": "Funcionalidade principal",
            "epic_id": epic.get("id", "E-001"),
            "as_a": "usuário",
            "i_want_to": "realizar ação principal",
            "so_that": "obter valor de negócio",
            "acceptance_criteria": ["Dado que...", "Quando...", "Então..."],
            "priority": "High",
            "status": "Pending",
            "dates": {"created_at": now},
        }
    ]
