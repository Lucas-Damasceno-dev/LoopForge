"""Schemas pydantic + endpoints CRUD de agentes (S2 — CRUD de agentes).

Mesmo padrão do memory.py: schemas no próprio arquivo do router.
AgentUpdate é PATCH-style (todos os campos opcionais) — no PUT, campos
omitidos mantêm o valor existente no ORM.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import AgentTemplate

agents_router = APIRouter(prefix="/api/v1/agents", tags=["Agents"])


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


# ─── Endpoints ───────────────────────────────────────────────────────────
@agents_router.get("", response_model=list[AgentResponse])
async def list_agents(session: AsyncSession = Depends(get_session)) -> list[AgentTemplate]:
    """Lista agentes ordenados por name (vazio = [])."""
    result = await session.execute(select(AgentTemplate).order_by(AgentTemplate.name))
    return list(result.scalars().all())


@agents_router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    payload: AgentCreate,
    session: AsyncSession = Depends(get_session),
) -> AgentTemplate:
    """Cria um agente (uuid gerado pelo ORM; name único → 422)."""
    existing = await session.execute(select(AgentTemplate).where(AgentTemplate.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="name already exists")
    agent = AgentTemplate(**payload.model_dump())
    session.add(agent)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=422, detail="name already exists") from None
    await session.refresh(agent)
    return agent


@agents_router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> AgentTemplate:
    """Retorna um agente pelo id."""
    agent = await session.get(AgentTemplate, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@agents_router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    session: AsyncSession = Depends(get_session),
) -> AgentTemplate:
    """Atualiza um agente (PATCH-style: campos None/omitidos mantêm o valor)."""
    agent = await session.get(AgentTemplate, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        dup = await session.execute(
            select(AgentTemplate).where(
                AgentTemplate.name == data["name"],
                AgentTemplate.id != agent_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(status_code=422, detail="name already exists")

    for field, value in data.items():
        if value is not None:
            setattr(agent, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=422, detail="name already exists") from None
    await session.refresh(agent)
    return agent


@agents_router.delete("/{agent_id}")
async def delete_agent(agent_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Remove um agente pelo id."""
    agent = await session.get(AgentTemplate, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await session.delete(agent)
    await session.commit()
    return {"deleted": True}
