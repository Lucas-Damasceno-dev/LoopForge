"""
GraphState TypedDict — o estado compartilhado entre todos os nós do pipeline.
"""

from __future__ import annotations

from typing import NotRequired, TypedDict


class GraphState(TypedDict):
    """Estado central do grafo LangGraph. Todos os nós leem/escrevem aqui.

    Chaves novas (stack_rationale, security_report, devops_report, run_id,
    task_id, auto_create_devops_files) são declaradas como NotRequired: são
    escritas/consumidas por nós específicos e nem sempre existem no estado
    inicial. Antes eram canais silenciosamente descartados pelo LangGraph.
    """

    # Entrada do usuário
    idea: str
    output_dir: str

    # Artefatos produzidos pelos nós
    epic: dict
    user_stories: list[dict]
    tech_spec: str
    contract_tests: str
    code: str
    test_report: dict
    security_review: dict
    devops_manifest: dict

    # Artefatos de auditoria e identificação da run — canais declarados para o
    # LangGraph NÃO descartar (antes eram escritos pelos nós e nunca persistiam
    # no checkpoint: stack_rationale do tech_lead, security_report/devops_report
    # do parallel_audit, run_id/task_id lidos pelo lessons, e o opt-in
    # auto_create_devops_files do devops).
    stack_rationale: NotRequired[str]
    security_report: NotRequired[str]
    devops_report: NotRequired[str]
    run_id: NotRequired[str]
    task_id: NotRequired[str]
    auto_create_devops_files: NotRequired[bool]

    # Metadados do projeto (carregados do ontology)
    ontology_path: str  # caminho pra examples/the-foundry/
    project_dir: str  # diretório do projeto alvo
    stack: str  # "react+node+postgres", "python+fastapi", etc.

    # Controle de fluxo
    next_agent: str
    attempt_count: int
    qa_attempt_count: int
    appsec_attempt_count: int
    max_retries: int
    error: str | None
    feedback_history: list[dict]

    # Config de LLM
    mock_llm: bool
    llm_provider: str
    llm_model_name: str
    llm_temperature: float

    # Modo interativo (human-in-the-loop), Roteamento Adaptativo e Read-Only
    is_interactive: bool
    read_only: bool
    routing_mode: str  # "full", "fast", "patch", "review-only", "explore"
    task_type: str  # "feature", "bugfix", "refactor", "simple", "full", "fast"
    complexity_level: str  # "mvp", "standard", "advanced"

    # Schema esperado para validação do próximo artefato
    expected_schema: str | None

    # Referência da persona ativa (carregada do ontology)
    persona_id: str | None

    # CircuitBreaker (M-08/M-10): snapshot serializável definido pelo
    # TaskDispatcher em _build_initial_state. PRECISA ser canal declarado —
    # o LangGraph descarta chaves fora do TypedDict, e sem ele o hard-stop
    # de budget do nó developer nunca via o estado (enforcement era morto).
    circuit_breaker: dict
