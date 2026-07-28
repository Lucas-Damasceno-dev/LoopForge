"""Schemas Pydantic para validação de entrada/saída da API REST."""

from datetime import datetime

from pydantic import BaseModel, Field

# ─── Requests ───────────────────────────────────────────────────────

class RunCreate(BaseModel):
    """Payload para criar uma nova execução de pipeline."""

    idea: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Ideia ou descrição de entrada para o pipeline",
    )
    stack: str = Field(
        default="python",
        max_length=20,
        description="Stack tecnológica alvo (python, javascript, etc.)",
    )


class RunUpdate(BaseModel):
    """Payload para atualizar campos de uma run existente."""

    status: str | None = Field(
        None,
        max_length=20,
        description="Novo status da run",
    )
    current_agent: str | None = Field(
        None,
        max_length=50,
        description="Agente atual em execução",
    )
    error_message: str | None = Field(
        None,
        max_length=5000,
        description="Mensagem de erro",
    )


# ─── Responses ──────────────────────────────────────────────────────

class RunResponse(BaseModel):
    """Resposta pública com dados de uma pipeline run."""

    id: str
    status: str
    idea: str
    current_agent: str | None
    stack: str
    total_cost: float
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunListResponse(BaseModel):
    """Resposta paginada de lista de runs."""

    items: list[RunResponse]
    total: int


class HealthResponse(BaseModel):
    """Resposta do endpoint de health check."""

    status: str = "ok"
    version: str = "6.0.0"
    database: str = "connected"