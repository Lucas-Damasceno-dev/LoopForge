"""
Nó Product Manager: quebra épico em user stories estruturadas.
Usa Pydantic structured output com schema do The Foundry.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode import call_llm_via_opencode


DEFAULT_PROMPT = """Você é um Product Manager. Quebre o épico abaixo em user stories detalhadas.

Cada user story DEVE ter TODOS os campos:
- id: {epic_id}-USXXX (sequencial)
- title: descritivo
- epic_id: {epic_id}
- as_a: persona (ex: "motorista de van", "pai de aluno")
- i_want_to: funcionalidade concreta
- so_that: benefício
- acceptance_criteria: lista de strings Given-When-Then
- priority: Medium (padrão)
- status: Pending (padrão)
- dates: use a data atual

Responda APENAS com o JSON. NÃO inclua texto explicativo."""


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

    # Reutiliza user stories se já geradas em etapa anterior do plano
    if state.get("user_stories"):
        print("--- INFO: PM reutilizando User Stories existentes no estado ---")
        return {**state, "next_agent": "tech_lead"}

    epic = state.get("epic")
    if not epic:
        raise ValueError("Épico não encontrado no estado")

    now_iso = datetime.now(UTC).isoformat()

    if state.get("mock_llm"):
        print("--- INFO: PM modo MOCK ---")
        stories = _mock_stories(epic)
        return {**state, "user_stories": stories, "next_agent": "tech_lead"}

    print("--- INFO: PM usando OpenCode via subprocesso ---")

    system_prompt = f"""Você é um Product Manager. Quebre o épico abaixo em user stories detalhadas.

Cada user story DEVE ter TODOS os campos:
- id: {epic.get("id", "E-001")}-USXXX (sequencial)
- title: descritivo
- epic_id: {epic.get("id", "E-001")}
- as_a: persona (ex: "motorista de van", "pai de aluno")
- i_want_to: funcionalidade concreta
- so_that: benefício
- acceptance_criteria: lista de strings Given-When-Then
- priority: Medium (padrão)
- status: Pending (padrão)
- dates: use a data atual

Responda APENAS com o JSON. NÃO inclua texto explicativo."""

    epic_context = f"""Épico:
Título: {epic.get("title", "")}
Descrição: {epic.get("description", "")}
Objetivos: {", ".join(epic.get("business_objectives", []))}
Escopo IN: {", ".join(epic.get("scope_in", []))}
Escopo OUT: {", ".join(epic.get("scope_out", []))}"""

    try:
        result = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=epic_context,
            schema_model=UserStoryList,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
        )
        stories = []
        for i, us in enumerate(result.get("stories", [])):
            us["id"] = f"{epic.get('id', 'E-001')}-US{i + 1:03d}"
            us["epic_id"] = epic.get("id", "E-001")
            us["dates"] = us.get("dates", {})
            us["dates"]["created_at"] = now_iso
            stories.append(us)
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
    now = datetime.now(UTC).isoformat()
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
