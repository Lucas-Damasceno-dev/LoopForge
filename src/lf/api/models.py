"""Modelos SQLAlchemy ORM para a API do LoopForge."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now_utc, onupdate=_now_utc
    )
