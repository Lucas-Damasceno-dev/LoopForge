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
    retry_fingerprints: NotRequired[list[str]]
    doom_loop_detected: NotRequired[bool]
    doom_loop_reason: NotRequired[str]

    # Fallback degradado — canal honesto de "mock por falha de LLM": os nós
    # setam degraded=True quando caem em resposta mock/heurística por ERRO de
    # LLM (não por modo mock explícito). O orquestrador lê esses canais para
    # marcar o run como degraded em vez de um completed enganoso.
    degraded: NotRequired[bool]
    degraded_reason: NotRequired[str]

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

    # Sandbox (roadmap 4.1): snapshot serializável definido pelo TaskDispatcher
    # em _setup_sandbox — git worktree isolada (.slim/worktrees/) para geração/
    # testes, com merge na main após aprovação QA+AppSec. Canal NotRequired (só
    # existe quando sandbox_enabled) e declarado para o LangGraph persistir no
    # checkpoint (o resume recria a worktree a partir dele).
    sandbox: NotRequired[dict]

    # Entrega Incremental por User Story (milestone v7 item 5.1): com
    # incremental_slices=True o pipeline gera/valida UM slice (user story) por
    # vez — Developer → QA → (test_writer → Developer → QA)* → Parallel Audit.
    # Todos os canais são NotRequired (flag off = estado idêntico ao atual);
    # precisam ser declarados senão o LangGraph descarta as chaves (mesmo
    # padrão de circuit_breaker/sandbox).
    incremental_slices: NotRequired[bool]
    slices: NotRequired[list[dict]]  # derivado de user_stories (slices.py)
    slice_index: NotRequired[int]
    slice_status: NotRequired[str]  # "pending" | "passed" | "failed"
    slice_test_report: NotRequired[dict]  # QA scoped, com slice_failed/regression_failed
    test_scope: NotRequired[str]  # "slice" | "full"
    slice_max_retries: NotRequired[int]  # limite de retries por slice (AdePipeline)
