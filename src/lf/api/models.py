"""Modelos ORM SQLAlchemy para a API do LoopForge.

Representa o domínio principal: execução de pipelines (runs).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lf.api.database import Base


class PipelineRun(Base):
    """Representa uma execução de pipeline no LoopForge.

    Cada run é uma instância única de execução do orquestrador,
    com estado, agente atual e métricas de custo.
    """

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="Status da run: pending | running | completed | failed | cancelled",
    )
    idea: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Ideia/descrição de entrada do pipeline",
    )
    current_agent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Agente atualmente em execução (cpo, pm, tech_lead, developer, qa)",
    )
    stack: Mapped[str] = mapped_column(
        String(20),
        default="python",
        comment="Stack tecnológica alvo",
    )
    total_cost: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        comment="Custo total acumulado da run",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Mensagem de erro se a run falhou",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Timestamp de criação",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Timestamp da última atualização",
    )

    def __repr__(self) -> str:
        return f"<PipelineRun id={self.id} status={self.status} idea={self.idea[:40]}>"