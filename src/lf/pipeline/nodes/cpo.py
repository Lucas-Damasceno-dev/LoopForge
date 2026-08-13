"""
Nó CPO: transforma ideia bruta em épico estruturado.
Usa OpenCode via subprocesso + Pydantic para structured output.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from ...pipeline.llm_factory import resolve_model
from ...pipeline.prompt_overrides import get_effective_prompt
from ...pipeline.state import GraphState
from ...runner.opencode.llm import call_llm_via_opencode, resolve_run_id

DEFAULT_PROMPT = """Você é um CPO (Chief Product Officer). Transforme a ideia abaixo em um épico de produto estruturado em JSON.

Preencha TODOS os campos obrigatórios:
- id: gere E-001
- title: título descritivo em português
- description: problema de negócio
- business_objectives: lista de objetivos
- hypothesis: hipótese a ser validada
- scope_in: itens dentro do escopo
- scope_out: itens fora do escopo
- success_metrics: métricas de sucesso
- stakeholders: {"owner": "CPO", "consulted": ["Product Manager", "UX/UI Designer", "CTO"]}
- dates: use a data atual

Foque no valor de negócio. Não inclua implementação técnica."""


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


def cpo(state: GraphState, config: Optional[RunnableConfig] = None) -> dict:  # noqa: UP045
    """Recebe a ideia e gera um épico estruturado."""
    print("---EXECUTANDO NÓ: CPO---")

    # Reutiliza épico se já gerado em etapa anterior do plano
    if state.get("epic"):
        print("--- INFO: CPO reutilizando Épico existente no estado ---")
        return {**state, "next_agent": "pm"}

    if state.get("mock_llm"):
        print("--- INFO: CPO modo MOCK ---")
        return {
            **state,
            "epic": _mock_epic(state.get("idea", "Mock idea")),
            "next_agent": "pm",
        }

    print("--- INFO: CPO usando OpenCode via subprocesso ---")

    now_iso = datetime.now(UTC).isoformat()

    system_prompt = get_effective_prompt("cpo", DEFAULT_PROMPT)

    complexity = state.get("complexity_level", "standard")
    complexity_prompt = ""
    if complexity == "mvp":
        complexity_prompt = "\nNÍVEL DE ESCOPO (MVP): Mantenha o épico enxuto, focado na funcionalidade essencial e no menor tempo de entrega possível."
    elif complexity == "advanced":
        complexity_prompt = "\nNÍVEL DE ESCOPO (AVANÇADO): Crie um épico completo, detalhado, com múltiplos módulos, métricas avançadas e análise de casos de borda."

    system_prompt = system_prompt + complexity_prompt

    # 🧬 Injeção opcional de genoma do projeto (config genome_injection, off por padrão)
    from ...pipeline.genome_injection import inject_genome

    system_prompt = inject_genome(
        system_prompt,
        project_dir=str(state.get("project_dir") or state.get("output_dir") or "."),
    )

    try:
        epic = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=f"Ideia do usuário: {state.get('idea', '')}",
            model=resolve_model(state),
            schema_model=EpicSchema,
            mock=state.get("mock_llm", False),
            circuit_breaker=state.get("circuit_breaker"),
            node="cpo",
            run_id=resolve_run_id(state, config),
        )
        epic["dates"] = {"created_at": now_iso, "started_at": now_iso}
    except Exception as e:
        print(f"--- ERRO CPO: {e} ---")
        # Fallback mock por falha de LLM → marca o run como degradado (o
        # orquestrador usa state["degraded"] para não reportar completed enganoso).
        return {
            **state,
            "epic": _mock_epic(state.get("idea", "")),
            "next_agent": "pm",
            "error": str(e),
            "degraded": True,
            "degraded_reason": str(e)[:200],
        }

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"epic_{epic['id']}.json")
        with open(path, "w") as f:
            json.dump(epic, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Épico salvo em {path} ---")

    return {**state, "epic": epic, "next_agent": "pm"}


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
        "dates": {"created_at": datetime.now(UTC).isoformat(), "started_at": datetime.now(UTC).isoformat()},
    }
