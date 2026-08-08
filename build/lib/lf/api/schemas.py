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
