"""Schemas pydantic de pipelines (S3 — editor de pipelines).

Mesmo padrão de agents.py: schemas no próprio arquivo do router (aqui ainda
sem router — endpoints CRUD entram na task 2). Validação apenas de shape
pydantic: ciclos/semântica de grafo ficam para a task 3 (validate).
PipelineUpdate é PATCH-style (todos os campos opcionais) — no PUT, campos
omitidos mantêm o valor existente no ORM.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
