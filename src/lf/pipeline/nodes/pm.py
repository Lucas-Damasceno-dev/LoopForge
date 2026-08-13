"""
Nó Product Manager: quebra épico em user stories estruturadas.
Usa Pydantic structured output com schema do The Foundry.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from ...pipeline.llm_factory import resolve_model
from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode.llm import call_llm_via_opencode, resolve_run_id

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


def product_manager(state: GraphState, config: Optional[RunnableConfig] = None) -> dict:  # noqa: UP045
    """Recebe épico e gera user stories."""
    print("---EXECUTANDO NÓ: Product Manager---")

    # Reutiliza user stories se já geradas em etapa anterior do plano
    if state.get("user_stories"):
        print("--- INFO: PM reutilizando User Stories existentes no estado ---")
        extra_slices = _build_slices_extra(state)
        return {**state, "next_agent": "tech_lead", **extra_slices}

    epic = state.get("epic")
    if not epic:
        raise ValueError("Épico não encontrado no estado")

    now_iso = datetime.now(UTC).isoformat()

    if state.get("mock_llm"):
        print("--- INFO: PM modo MOCK ---")
        mock_stories = _mock_stories(epic)
        extra_slices = _build_slices_extra(state, stories=mock_stories)
        return {**state, "user_stories": mock_stories, "next_agent": "tech_lead", **extra_slices}

    print("--- INFO: PM usando OpenCode via subprocesso ---")

    system_prompt = get_effective_prompt("pm", DEFAULT_PROMPT.format(epic_id=epic.get("id", "E-001")))

    # 🧬 Injeção opcional de genoma do projeto (config genome_injection, off por padrão)
    from ...pipeline.genome_injection import inject_genome

    system_prompt = inject_genome(
        system_prompt,
        project_dir=str(state.get("project_dir") or state.get("output_dir") or "."),
    )

    epic_context = f"""Épico:
Título: {epic.get("title", "")}
Descrição: {epic.get("description", "")}
Objetivos: {", ".join(epic.get("business_objectives", []))}
Escopo IN: {", ".join(epic.get("scope_in", []))}
Escopo OUT: {", ".join(epic.get("scope_out", []))}"""

    # Fallback degradado: setado no except quando o mock é usado por falha de LLM
    degraded = False
    degraded_reason = ""
    stories: list[dict] = []

    try:
        result = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=epic_context,
            model=resolve_model(state),
            schema_model=UserStoryList,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
            node="pm",
            run_id=resolve_run_id(state, config),
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
        # Fallback mock por falha de LLM → marca o run como degradado.
        degraded = True
        degraded_reason = str(e)[:200]

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for us in stories:
            path = os.path.join(output_dir, f"us_{us['id']}.json")
            with open(path, "w") as f:
                json.dump(us, f, indent=2, ensure_ascii=False)

    extra = {"degraded": True, "degraded_reason": degraded_reason} if degraded else {}
    extra_slices = _build_slices_extra(state, stories=stories)
    return {**state, "user_stories": stories, "next_agent": "tech_lead", **extra, **extra_slices}


def _build_slices_extra(state: Any, stories: list | None = None) -> dict:
    """Deriva os slices incrementais das user stories, se a flag estiver ligada.

    Retorna {} (byte-idêntico ao atual) quando ``incremental_slices`` está off;
    com a flag ligada, devolve ``{"slices": [...]}`` capado por
    ``AdePipeline.max_slices`` (lido em call-time). O nó developer/test_writer/
    qa consome os slices via estado.
    """
    if not state.get("incremental_slices"):
        return {}
    try:
        from ...config.loader import load_ade_config

        max_slices = load_ade_config().pipeline.max_slices
    except Exception:
        max_slices = 8
    from .slices import build_slices

    user_stories = stories if stories is not None else state.get("user_stories", [])
    return {"slices": build_slices(user_stories, max_slices=max_slices)}


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
