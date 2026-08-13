"""Schemas Pydantic para validação de requests/responses da API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

RoutingMode = Literal["full", "fast", "patch", "review-only", "explore"]


class RunCreate(BaseModel):
    idea: str = Field(..., description="Descrição da funcionalidade ou ideia")
    stack: str = Field("python", description="Stack de tecnologia")
    mock_llm: bool = Field(False, description="Usar modo LLM mock")
    routing_mode: RoutingMode = Field("full", description="Modo de roteamento: full ou fast")
    interactive: bool = Field(False, description="Pausar após nós para aprovação humana (HITL)")
    model: str | None = Field(None, description="Modelo LLM override para a run (vence env/config)")


class RunUpdate(BaseModel):
    status: str | None = Field(None, description="pending, running, done, failed")
    current_node: str | None = Field(None, description="Nó atualmente em execução")
    logs: str | None = Field(None, description="Logs acumulados")
    duration_seconds: float | None = Field(None, description="Duração em segundos")


class RunResponse(BaseModel):
    id: str
    idea: str
    stack: str
    status: str
    current_node: str | None = None
    logs: str | None = None
    duration_seconds: float = 0.0
    # Degradação da run (mock fallback, provider degradado etc.) — ADITIVO.
    degraded: bool = False
    degraded_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    items: list[RunResponse]
    total: int


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "6.0.0"


class HumanDecisionCreate(BaseModel):
    gate_node: str = Field(..., description="Nó do gate humano (ex: developer, qa, appsec)")
    action: str = Field(
        ...,
        description="approve, retry, adjust_prompt, adjust_state, abort",
    )
    feedback_category: str | None = Field(None, description="bug, style, missing_feature, general")
    feedback_message: str | None = Field(None, description="Mensagem de feedback")
    user: str = Field("human_operator", description="Identificador do operador")
    # C3 (M-12): patch de estado aplicado ao checkpoint quando action=adjust_state.
    state_patch: dict[str, Any] | None = Field(
        default=None,
        description="Patch de estado (dict JSON) aplicado ao checkpoint via adjust_state",
    )

    @field_validator("state_patch", mode="before")
    @classmethod
    def _validate_state_patch(cls, v: Any) -> Any:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError("state_patch deve ser um objeto JSON (dict) válido")
        return v


class HumanDecisionResponse(BaseModel):
    id: str
    run_id: str
    gate_node: str
    action: str
    feedback_category: str | None = None
    feedback_message: str | None = None
    user: str
    timestamp: datetime

    model_config = {"from_attributes": True}


class CostBudget(BaseModel):
    """Budget efetivo de uma run (M-08/M-10): fonte única ade.yaml + overrides."""

    max_usd: float
    percent_used: float


class CostNode(BaseModel):
    """Custo agregado por nó da run (D1/Fase D): base dos chips de custo na UI."""

    node: str
    spent_usd: float
    estimated: bool


class CostResponse(BaseModel):
    """Custo acumulado de uma run em llm_costs + estado do budget (M-08/M-10)."""

    run_id: str
    spent_usd: float
    estimated: bool
    budget: CostBudget
    budget_warning: bool
    # D1 (Fase D): breakdown por nó — campo ADITIVO (SPA depende dos demais).
    nodes: list[CostNode] = Field(default_factory=list)


class BudgetOverrideRequest(BaseModel):
    """Corpo do POST /runs/{id}/cost/override (M-10)."""

    max_usd: float | None = Field(
        None,
        gt=0,
        description="Novo limite de budget em USD; ausente/nulo = usa ade.yaml budget.max_usd",
    )


class MCPToolCallRequest(BaseModel):
    """Corpo do POST /api/v1/mcp/servers/{name}/tools/{tool} (D2)."""

    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Argumentos da tool MCP (JSON); ausente/vazio = {}",
    )


# ─── Artifacts (InspectDrawer da SPA) ────────────────────────────────────
class ArtifactTokens(BaseModel):
    """Tokens + custo LLM agregados por nó (tabela llm_costs)."""

    node: str
    model: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    estimated: bool = False


class NodeArtifact(BaseModel):
    """Artifacts de um nó do DAG extraídos do último checkpoint."""

    output: dict[str, Any] = Field(default_factory=dict)


class CircuitBreakerSnapshot(BaseModel):
    """Snapshot serializável do CircuitBreaker (canal circuit_breaker)."""

    state: str | None = None
    consecutive_failures: int = 0
    total_iterations: int = 0
    total_cost: float = 0.0
    max_consecutive_failures: int | None = None
    max_iterations: int | None = None
    max_total_cost: float | None = None
    cost_per_iteration: float | None = None
    reset_timeout: float | None = None
    last_failure_time: float | None = None


class ArtifactLesson(BaseModel):
    """Lição aprendida associada à run (tabela lessons)."""

    id: int
    run_id: str
    lesson_text: str
    created_at: float


class ArtifactsResponse(BaseModel):
    """GET /api/v1/runs/{id}/artifacts — artifacts + tokens + estado da run."""

    run_id: str
    node_artifacts: dict[str, NodeArtifact] = Field(default_factory=dict)
    tokens: list[ArtifactTokens] = Field(default_factory=list)
    degraded: bool = False
    degraded_reason: str | None = None
    circuit_breaker: CircuitBreakerSnapshot | None = None
    lessons: list[ArtifactLesson] = Field(default_factory=list)


class RunFileItem(BaseModel):
    """Arquivo gerado no diretório de saída da run."""

    path: str
    size: int
    content: str | None = None
    is_binary: bool = False


class RunFilesResponse(BaseModel):
    """GET /api/v1/runs/{id}/files — lista e conteúdo dos arquivos gerados."""

    run_id: str
    files: list[RunFileItem] = Field(default_factory=list)


# ─── Terminal & Command Runner ──────────────────────────────────────
class ExecCommandRequest(BaseModel):
    command: str = Field(..., description="Comando bash a executar no workspace da run")
    timeout_seconds: int = Field(15, ge=1, le=60, description="Tempo limite em segundos")


class ExecCommandResponse(BaseModel):
    run_id: str
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float


class TerminalInfoResponse(BaseModel):
    run_id: str
    workspace_path: str | None
    exists: bool


# ─── AST & Dependency Analysis ─────────────────────────────────────
class AstSymbolInfo(BaseModel):
    name: str
    kind: str
    line_number: int
    docstring: str | None = None


class AstModuleInfo(BaseModel):
    file_path: str
    language: str
    total_lines: int
    symbols: list[AstSymbolInfo] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)


class AstEdge(BaseModel):
    source_file: str
    target_module: str
    import_type: str = "import"


class AstAnalysisResponse(BaseModel):
    run_id: str
    modules: list[AstModuleInfo] = Field(default_factory=list)
    external_packages: list[str] = Field(default_factory=list)
    dependency_graph: list[AstEdge] = Field(default_factory=list)


# ─── Code Coverage ─────────────────────────────────────────────────
class FileCoverageItem(BaseModel):
    file_path: str
    total_lines: int
    covered_lines: int
    missed_lines: int
    percentage: float


class CoverageReportResponse(BaseModel):
    run_id: str
    total_lines: int
    covered_lines: int
    coverage_percentage: float
    files: list[FileCoverageItem] = Field(default_factory=list)
    source: str = "report"


