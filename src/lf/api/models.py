"""Modelos SQLAlchemy ORM para a API do LoopForge."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from lf.api.database import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(UTC)


class PipelineRun(Base):
    """Modelo ORM para a tabela 'pipeline_runs'."""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    stack: Mapped[str] = mapped_column(String(50), default="python")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    current_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    # Degradação da run (mock fallback, provider degradado) — colunas aditivas
    # garantidas via ALTER TABLE em app._ensure_pipeline_runs_degraded_columns.
    degraded: Mapped[bool] = mapped_column(default=False)
    degraded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ADR-0003 (M-02): identidade run↔thread 1:1 persistida — a thread
    # LangGraph canônica da run (`run-{id}`) e a run de origem em forks
    # (NULL em runs raiz). Permite resume/fork/time-travel por chave real.
    thread_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class HumanDecisionModel(Base):
    """Modelo ORM para a tabela 'human_decisions'."""

    __tablename__ = "human_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    gate_node: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)  # approve, retry, adjust_prompt, abort
    feedback_category: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # bug, style, missing_feature, general
    feedback_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    user: Mapped[str] = mapped_column(String(50), default="human_operator")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)


class AgentTemplate(Base):
    """Modelo ORM para a tabela 'agent_templates'.

    Colunas espelhando os schemas pydantic de AgentBase (lf/api/agents.py).
    env_vars/tools_allowlist/permissions usam JSON (precedente: events.payload,
    eventos.py) — ok no SQLite; create_all cria a tabela nova sem migração.
    `name` é unique (chave natural do agente).
    """

    __tablename__ = "agent_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="default")
    temperature: Mapped[float] = mapped_column(Float, default=0.7)
    max_retries: Mapped[int] = mapped_column(default=2)
    timeout_seconds: Mapped[int] = mapped_column(default=300)
    env_vars: Mapped[dict] = mapped_column(JSON, default=dict)
    tools_allowlist: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    stack: Mapped[str] = mapped_column(String(50), default="python")
    budget_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)
