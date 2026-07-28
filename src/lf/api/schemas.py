"""Schemas Pydantic para validação de requests/responses da API."""
from datetime import datetime

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    idea: str = Field(..., description="Descrição da funcionalidade ou ideia")
    stack: str = Field("python", description="Stack de tecnologia")


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
