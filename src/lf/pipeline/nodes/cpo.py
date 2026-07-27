#-*- coding: utf-8 -*-
"""
Nó CPO: transforma ideia bruta em épico estruturado.
Usa Pydantic structured output com o schema do The Foundry.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ..llm_factory import get_llm_client
from ...pipeline.state import GraphState


class EpicSchema(BaseModel):
    """Schema Pydantic baseado em epic_schema.json do The Foundry."""
    id: str = Field(..., description="Identificador único no formato E-XXX")
    title: str = Field(..., description="Título descritivo do épico")
    description: str = Field(..., description="Problema de negócio a ser resolvido")
    business_objectives: list[str] = Field(..., description="Objetivos de negócio")
    hypothesis: str = Field(..., description="Hipótese validada com a entrega")
    scope_in: list[str] = Field(..., description="Dentro do escopo")
    scope_out: list[str] = Field(..., description="Fora do escopo")
    success_metrics: list[str] = Field(..., description="Métricas de sucesso")
    stakeholders: dict = Field(..., description="owner + consulted")
    dates: dict = Field(..., description="created_at, started_at, completed_at")


def cpo(state: GraphState) -> dict:
    """Recebe a ideia e gera um épico estruturado."""
    print("---EXECUTANDO NÓ: CPO---")

    if state.get("mock_llm"):
        print("--- INFO: CPO modo MOCK ---")
        return {
            **state,
            "epic": _mock_epic(state.get("idea", "Mock idea")),
            "next_agent": "product_manager",
        }

    llm = get_llm_client(
        state["llm_provider"],
        state["llm_model_name"],
        temperature=state.get("llm_temperature", 0.3),
    )
    llm_structured = llm.with_structured_output(EpicSchema)
    print(f"--- INFO: CPO usando {state['llm_provider']}/{state['llm_model_name']} ---")

    now_iso = datetime.now(timezone.utc).isoformat()

    prompt = f"""Você é um CPO (Chief Product Officer). Transforme a ideia abaixo em um épico de produto estruturado em JSON.

Preencha TODOS os campos obrigatórios:
- id: gere E-001
- title: título descritivo em português
- description: problema de negócio
- business_objectives: lista de objetivos
- hypothesis: hipótese a ser validada
- scope_in: itens dentro do escopo
- scope_out: itens fora do escopo
- success_metrics: métricas de sucesso
- stakeholders: {{"owner": "CPO", "consulted": ["Product Manager", "UX/UI Designer", "CTO"]}}
- dates: use a data atual

Foque no valor de negócio. Não inclua implementação técnica.

Ideia do usuário: {state.get('idea', '')}"""

    try:
        epic_pydantic = llm_structured.invoke(prompt)
        epic = epic_pydantic.model_dump()
        epic["dates"] = {"created_at": now_iso, "started_at": now_iso}
    except Exception as e:
        print(f"--- ERRO CPO: {e} ---")
        return {**state, "epic": _mock_epic(state.get("idea", "")), "next_agent": "product_manager", "error": str(e)}

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"epic_{epic['id']}.json")
        with open(path, "w") as f:
            json.dump(epic, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Épico salvo em {path} ---")

    return {**state, "epic": epic, "next_agent": "product_manager"}


def _mock_epic(idea: str) -> dict:
    return {
        "id": "E-001",
        "title": f"Épico: {idea[:50]}",
        "description": idea,
        "business_objectives": ["Objetivo 1", "Objetivo 2"],
        "hypothesis": "Hipótese de valor",
        "scope_in": ["Funcionalidade principal"],
        "scope_out": ["Recursos avançados"],
        "success_metrics": ["Métrica 1", "Métrica 2"],
        "stakeholders": {"owner": "CPO", "consulted": ["Product Manager", "UX/UI Designer", "CTO"]},
        "dates": {"created_at": datetime.now(timezone.utc).isoformat(),
                  "started_at": datetime.now(timezone.utc).isoformat()},
    }
