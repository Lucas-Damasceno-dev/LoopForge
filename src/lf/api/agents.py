"""Schemas pydantic de agentes (S2 — CRUD de agentes).

Mesmo padrão do memory.py: schemas no próprio arquivo do router.
AgentUpdate é PATCH-style (todos os campos opcionais) — no PUT, campos
omitidos mantêm o valor existente no ORM.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Campos base de um agente (create e response)."""

    name: str = Field(..., min_length=1, description="Nome único do agente")
    description: str = Field(default="", description="Descrição do agente")
    prompt: str = Field(..., min_length=1, description="Prompt do agente")
    model: str = Field(default="default", description="Modelo LLM usado pelo agente")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Temperatura de amostragem (0-2)")
    max_retries: int = Field(default=2, ge=0, description="Máximo de tentativas de execução")
    timeout_seconds: int = Field(default=300, ge=1, description="Timeout de execução em segundos")
    env_vars: dict[str, str] = Field(default_factory=dict, description="Variáveis de ambiente do agente")
    tools_allowlist: list[str] = Field(default_factory=list, description="Tools permitidas ao agente")
    permissions: list[str] = Field(default_factory=list, description="Permissões concedidas ao agente")
    stack: str = Field(default="python", description="Stack tecnológica (ex.: python)")
    budget_usd: float = Field(default=0.0, ge=0, description="Orçamento máximo em USD (0 = ilimitado)")


class AgentCreate(AgentBase):
    """Payload para criar um agente."""


class AgentUpdate(BaseModel):
    """Payload para atualizar um agente (PATCH-style no PUT).

    Todos os campos são opcionais: campos omitidos mantêm o valor existente.
    """

    name: str | None = Field(default=None, min_length=1, description="Novo nome")
    description: str | None = Field(default=None, description="Nova descrição")
    prompt: str | None = Field(default=None, min_length=1, description="Novo prompt")
    model: str | None = Field(default=None, description="Novo modelo LLM")
    temperature: float | None = Field(default=None, ge=0, le=2, description="Nova temperatura")
    max_retries: int | None = Field(default=None, ge=0, description="Novo máximo de tentativas")
    timeout_seconds: int | None = Field(default=None, ge=1, description="Novo timeout em segundos")
    env_vars: dict[str, str] | None = Field(default=None, description="Novas variáveis de ambiente")
    tools_allowlist: list[str] | None = Field(default=None, description="Nova lista de tools permitidas")
    permissions: list[str] | None = Field(default=None, description="Novas permissões")
    stack: str | None = Field(default=None, description="Nova stack")
    budget_usd: float | None = Field(default=None, ge=0, description="Novo orçamento em USD")


class AgentResponse(AgentBase):
    """Agente como devolvido pela API."""

    id: str = Field(..., description="Id do agente (uuid)")
    created_at: datetime = Field(..., description="Timestamp de criação")
    updated_at: datetime = Field(..., description="Timestamp da última atualização")
