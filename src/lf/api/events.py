"""EventBus: emissor único de eventos com journal persistido e envelope v1.

Implementa o ADR-0002 (event journal + envelope v1): cada evento publicado é
persistido na tabela ``events`` (telemetry.sqlite) e broadcastado via WebSocket
no formato ``{seq, event, run_id, timestamp, payload}`` (03-contratos-api.md).
O backfill REST (GET /runs/{id}/events) consumirá ``list_events``.
"""
import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from lf.api import database
from lf.api.database import Base
from lf.api.websocket_manager import ws_manager


def _generate_uuid() -> str:
    return str(uuid.uuid4())


def _now_utc() -> datetime:
    return datetime.now(UTC)


class Event(Base):
    """Modelo ORM para a tabela 'events' — journal persistido de eventos."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)  # monotônico por run, 1-based
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)


class EventBus:
    """Emissor único: persiste no journal e agenda o broadcast WS do envelope v1."""

    def __init__(self) -> None:
        self._mem_seq: dict[str, int] = {}

    async def _next_seq(self, session: AsyncSession, run_id: str) -> int:
        """Próximo seq da run: COUNT+1 sobre os eventos persistidos no journal."""
        result = await session.execute(select(func.count(Event.id)).where(Event.run_id == run_id))
        return int(result.scalar_one()) + 1

    def _to_envelope(self, event: Event) -> dict:
        """Monta o envelope v1: {seq, event, run_id, timestamp, payload}."""
        ts = event.created_at
        if ts.tzinfo is None:
            # SQLite não persiste timezone: assume UTC (default do modelo).
            ts = ts.replace(tzinfo=UTC)
        return {
            "seq": event.seq,
            "event": event.event_type,
            "run_id": event.run_id,
            "timestamp": ts.isoformat(),
            "payload": event.payload,
        }

    def _broadcast(self, envelope: dict) -> None:
        """Agenda o broadcast WS no loop ativo; sem loop ativo, apenas persiste."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ws_manager.broadcast(envelope))
        except RuntimeError:
            pass

    async def publish(self, run_id: str, event_type: str, payload: dict) -> dict:
        """Persiste o evento no journal e agenda o broadcast WS do envelope v1."""
        if database.session_factory is not None:
            async with database.session_factory() as session:
                seq = await self._next_seq(session, run_id)
                event = Event(run_id=run_id, seq=seq, event_type=event_type, payload=payload)
                session.add(event)
                await session.commit()
                await session.refresh(event)
                envelope = self._to_envelope(event)
        else:
            # Fallback sem DB inicializado (ex.: CLI puro): seq em memória.
            seq = self._mem_seq.get(run_id, 0) + 1
            self._mem_seq[run_id] = seq
            envelope = {
                "seq": seq,
                "event": event_type,
                "run_id": run_id,
                "timestamp": _now_utc().isoformat(),
                "payload": payload,
            }
        self._broadcast(envelope)
        return envelope

    async def list_events(self, run_id: str, after_seq: int = 0, limit: int = 200) -> list[dict]:
        """Lista envelopes v1 persistidos da run, ordenados por seq (backfill).

        ``after_seq`` exclui eventos com seq <= after_seq (paginação);
        ``limit`` limita a quantidade retornada (default 200).
        """
        if database.session_factory is None:
            return []
        async with database.session_factory() as session:
            stmt = (
                select(Event)
                .where(Event.run_id == run_id, Event.seq > after_seq)
                .order_by(Event.seq.asc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            events = result.scalars().all()
        return [self._to_envelope(e) for e in events]


event_bus = EventBus()
