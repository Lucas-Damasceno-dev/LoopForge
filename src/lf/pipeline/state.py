"""
GraphState TypedDict — o estado compartilhado entre todos os nós do pipeline.
"""
from __future__ import annotations

from typing import TypedDict


class GraphState(TypedDict):
    """Estado central do grafo LangGraph. Todos os nós leem/escrevem aqui."""

    # Entrada do usuário
    idea: str
    output_dir: str

    # Artefatos produzidos pelos nós
    epic: dict
    user_stories: list[dict]
    tech_spec: str
    code: str
    test_report: dict
    security_review: dict
    devops_manifest: dict


    # Metadados do projeto (carregados do ontology)
    ontology_path: str  # caminho pra examples/the-foundry/
    project_dir: str  # diretório do projeto alvo
    stack: str  # "react+node+postgres", "python+fastapi", etc.

    # Controle de fluxo
    next_agent: str
    attempt_count: int
    max_retries: int
    error: str | None
    feedback_history: list[dict]

    # Config de LLM
    mock_llm: bool
    llm_provider: str
    llm_model_name: str
    llm_temperature: float

    # Modo interativo (human-in-the-loop) e Roteamento Adaptativo
    is_interactive: bool
    routing_mode: str  # "full" ou "fast"
    task_type: str     # "feature", "bugfix", "refactor", "simple", "full", "fast"

    # Schema esperado para validação do próximo artefato
    expected_schema: str | None

    # Referência da persona ativa (carregada do ontology)
    persona_id: str | None
