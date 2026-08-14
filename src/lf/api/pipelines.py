"""Schemas pydantic + endpoints CRUD de pipelines (S3 — editor de pipelines).

Mesmo padrão de agents.py: schemas no próprio arquivo do router.
PipelineUpdate é PATCH-style (todos os campos opcionais) — no PUT, campos
omitidos mantêm o valor existente no ORM. Validação de shape pydantic aqui;
ciclos/semântica de grafo ficam para a task 3 (validate).
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import AgentTemplate, PipelineTemplate

pipelines_router = APIRouter(prefix="/api/v1/pipelines", tags=["Pipelines"])

NODE_TYPES = Literal["agent", "split", "merge", "input", "output", "gate"]
EDGE_TYPES = Literal["sequential", "parallel", "conditional", "retry"]


class PipelineNode(BaseModel):
    """Nó de um pipeline (referência a um agente ou operador estrutural)."""

    id: str = Field(..., min_length=1, description="Identificador único do nó no pipeline")
    type: NODE_TYPES = Field(..., description="Tipo do nó")
    agent_id: str | None = Field(default=None, description="ID do agente (obrigatório p/ type=agent)")
    config: dict[str, Any] = Field(default_factory=dict, description="Config livre do nó (extensão)")


class PipelineEdge(BaseModel):
    """Aresta entre nós. condition/max_retries vivem na aresta (não no nó)."""

    source: str = Field(..., min_length=1, description="Nó de origem")
    target: str = Field(..., min_length=1, description="Nó de destino")
    type: EDGE_TYPES = Field(default="sequential", description="Tipo da aresta")
    condition: str | None = Field(default=None, description="Condição (obrigatória p/ type=conditional)")
    max_retries: int = Field(default=2, ge=0, description="Máx. tentativas (usado p/ type=retry)")

    @model_validator(mode="after")
    def _conditional_requires_condition(self) -> "PipelineEdge":
        if self.type == "conditional" and not self.condition:
            raise ValueError("aresta condicional exige 'condition'")
        return self


class PipelineBase(BaseModel):
    """Campos base de um pipeline (create e response)."""

    name: str = Field(..., min_length=1, description="Nome único do pipeline")
    description: str = Field(default="", description="Descrição do pipeline")
    nodes: list[PipelineNode] = Field(default_factory=list, description="Nós do pipeline")
    edges: list[PipelineEdge] = Field(default_factory=list, description="Arestas do pipeline")


class PipelineCreate(PipelineBase):
    """Payload para criar um pipeline."""


class PipelineUpdate(BaseModel):
    """Payload para atualizar um pipeline (PATCH-style no PUT).

    Todos os campos são opcionais: campos omitidos mantêm o valor existente.
    """

    name: str | None = Field(default=None, min_length=1, description="Novo nome")
    description: str | None = Field(default=None, description="Nova descrição")
    nodes: list[PipelineNode] | None = Field(default=None, description="Novos nós")
    edges: list[PipelineEdge] | None = Field(default=None, description="Novas arestas")


class PipelineResponse(PipelineBase):
    """Pipeline como retornado pela API: base + id e timestamps."""

    id: str = Field(..., description="UUID do pipeline")
    created_at: datetime = Field(..., description="Data de criação")
    updated_at: datetime = Field(..., description="Data da última atualização")


# ─── Endpoints ───────────────────────────────────────────────────────────
@pipelines_router.get("", response_model=list[PipelineResponse])
async def list_pipelines(session: AsyncSession = Depends(get_session)) -> list[PipelineTemplate]:
    """Lista pipelines ordenados por name (vazio = [])."""
    result = await session.execute(select(PipelineTemplate).order_by(PipelineTemplate.name))
    return list(result.scalars().all())


@pipelines_router.post("", response_model=PipelineResponse, status_code=201)
async def create_pipeline(
    payload: PipelineCreate,
    session: AsyncSession = Depends(get_session),
) -> PipelineTemplate:
    """Cria um pipeline (uuid gerado pelo ORM; name único → 422)."""
    existing = await session.execute(select(PipelineTemplate).where(PipelineTemplate.name == payload.name))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=422, detail="name already exists")
    pipeline = PipelineTemplate(**payload.model_dump())
    session.add(pipeline)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=422, detail="name already exists") from None
    await session.refresh(pipeline)
    return pipeline


@pipelines_router.get("/{pipeline_id}", response_model=PipelineResponse)
async def get_pipeline(pipeline_id: str, session: AsyncSession = Depends(get_session)) -> PipelineTemplate:
    """Retorna um pipeline pelo id."""
    pipeline = await session.get(PipelineTemplate, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline


@pipelines_router.put("/{pipeline_id}", response_model=PipelineResponse)
async def update_pipeline(
    pipeline_id: str,
    payload: PipelineUpdate,
    session: AsyncSession = Depends(get_session),
) -> PipelineTemplate:
    """Atualiza um pipeline (PATCH-style: campos None/omitidos mantêm o valor)."""
    pipeline = await session.get(PipelineTemplate, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        dup = await session.execute(
            select(PipelineTemplate).where(
                PipelineTemplate.name == data["name"],
                PipelineTemplate.id != pipeline_id,
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(status_code=422, detail="name already exists")

    for field, value in data.items():
        if value is not None:
            setattr(pipeline, field, value)

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=422, detail="name already exists") from None
    await session.refresh(pipeline)
    return pipeline


@pipelines_router.delete("/{pipeline_id}")
async def delete_pipeline(pipeline_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """Remove um pipeline pelo id."""
    pipeline = await session.get(PipelineTemplate, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    await session.delete(pipeline)
    await session.commit()
    return {"deleted": True}


@pipelines_router.post("/{pipeline_id}/validate")
async def validate_pipeline_endpoint(
    pipeline_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Valida um pipeline salvo (referências, ciclos, tetos, agentes).

    known_agents = ids de agent_templates + SPECIAL_AGENT_IDS (ids do pipeline
    nativo). Sempre 200 com {"valid": bool, "errors": [...]}; 404 se o
    pipeline não existe. Import local do validador evita ciclo de imports
    (pipeline_validator importa os schemas deste módulo).
    """
    from lf.api.pipeline_validator import validate_pipeline

    row = await session.get(PipelineTemplate, pipeline_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    agents = await session.execute(select(AgentTemplate.id))
    known_agents = {row_id for (row_id,) in agents.all()}

    pipeline = PipelineBase(name=row.name, description=row.description, nodes=row.nodes, edges=row.edges)
    errors = validate_pipeline(pipeline, known_agents)
    return {"valid": not errors, "errors": errors}
