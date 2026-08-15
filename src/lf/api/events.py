"""EventBus: emissor único de eventos com journal persistido e envelope v1.

Implementa o ADR-0002 (event journal + envelope v1): cada evento publicado é
persistido na tabela ``events`` (telemetry.sqlite) e broadcastado via WebSocket
no formato ``{seq, event, run_id, timestamp, payload}`` (03-contratos-api.md).
O backfill REST (GET /runs/{id}/events) consumirá ``list_events``.
"""

import asyncio
import json
import logging
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from redis.asyncio import Redis
from sqlalchemy import JSON, DateTime, Integer, String, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from lf.api import database
from lf.api.database import Base
from lf.api.websocket_manager import ws_manager

logger = logging.getLogger(__name__)

# Identidade do worker (estável por processo): usada p/ dedup no canal
# lf:events — o envelope do canal carrega ``origin``; cada worker pula a
# própria mensagem (o broadcast local do publish já entregou aos seus WS).
WORKER_ID = uuid.uuid4().hex


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


class EventSeq(Base):
    """Contador de seq por run (tabela de sequência) para alocação atômica.

    Uma linha por run_id; o próximo seq é alocado com ``UPDATE ... RETURNING``
    (incremento atômico sob o lock de escrita do SQLite), em vez do antigo
    COUNT+1 que duplicava seq em publishes concorrentes.
    """

    __tablename__ = "event_seq"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    last_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def _load_checkpoints_for_thread(thread_id: str) -> list[dict]:
    """Carrega os checkpoints LangGraph do thread (C5/M-02), para rodar em to_thread.

    Lê a tabela ``checkpoints`` de ``.loopforge/trajectories.db`` (o MESMO banco
    do AsyncSqliteSaver da ADE) usando a conexão do ``SqliteSaver`` síncrono
    (factory ``create_sync_checkpointer`` em checkpointer.py) e desserializa o
    blob ``checkpoint`` (msgpack via ``serde.loads_typed``) e o ``metadata``
    (JSON puro). Sem banco, sem thread ou em erro de leitura → lista vazia
    (telemetria nunca derruba o request).
    """
    db_path = Path(".loopforge/trajectories.db").resolve()
    if not db_path.exists():
        return []
    try:
        from lf.pipeline.checkpointer import create_sync_checkpointer

        saver = create_sync_checkpointer(db_path)
        try:
            saver.setup()
            cursor = saver.conn.cursor()
            cursor.execute(
                "SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata "
                "FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id ASC",
                (thread_id,),
            )
            rows = cursor.fetchall()
            cursor.close()
        finally:
            saver.conn.close()

        items: list[dict] = []
        for checkpoint_id, parent_checkpoint_id, cp_type, checkpoint_blob, metadata_blob in rows:
            try:
                checkpoint = saver.serde.loads_typed((cp_type, checkpoint_blob))
            except Exception:
                checkpoint = {}
            try:
                metadata = json.loads(metadata_blob) if metadata_blob else {}
            except Exception:
                metadata = {}
            items.append(
                {
                    "checkpoint_id": checkpoint_id,
                    "parent_checkpoint_id": parent_checkpoint_id,
                    "type": cp_type,
                    "metadata": metadata,
                    "checkpoint": dict(checkpoint),
                }
            )
        return items
    except Exception as exc:
        logger.warning("Falha ao ler checkpoints da thread %s: %s", thread_id, exc)
        return []


class EventBus:
    """Emissor único: persiste no journal e agenda o broadcast WS do envelope v1."""

    def __init__(self) -> None:
        self._mem_seq: dict[str, int] = {}
        self._mem_lock = threading.Lock()
        self._redis: Redis | None = None  # publicador de lf:events (multi-worker)

    def configure_redis(self, redis: Redis) -> None:
        """Ativa publicador redis (canal lf:events) — multi-worker WS."""
        self._redis = redis

    async def _next_seq(self, session: AsyncSession, run_id: str) -> int:
        """Próximo seq da run, alocado atomicamente via UPDATE...RETURNING.

        Mecanismo: tabela ``event_seq`` (contador por run). O upsert cria a
        linha (last_seq=0) e o ``UPDATE ... RETURNING last_seq`` incrementa e
        devolve o novo valor — tudo na MESMA transação do INSERT do evento,
        então rollback desfaz o incremento (seq permanece contíguo). O SQLite
        serializa escritores (WAL + busy_timeout=5000): UPDATEs concorrentes na
        mesma linha esperam o lock e devolvem valores distintos — seq único e
        estritamente crescente por run, mesmo multi-processo. O antigo COUNT+1
        era não-atômico e duplicava seq em publishes concorrentes.
        """
        await session.execute(
            text("INSERT INTO event_seq (run_id, last_seq) VALUES (:rid, 0) ON CONFLICT (run_id) DO NOTHING"),
            {"rid": run_id},
        )
        result = await session.execute(
            text("UPDATE event_seq SET last_seq = last_seq + 1 WHERE run_id = :rid RETURNING last_seq"),
            {"rid": run_id},
        )
        row = result.first()
        if row is None:
            raise RuntimeError(f"Falha ao alocar seq atômico para a run {run_id}")
        return int(row[0])

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
        """Agenda o envio WS no loop ativo; sem loop ativo, apenas persiste.

        Todo envelope carrega run_id (journal por run): o evento vai ao canal da
        run via ``send_to_run`` (isolamento M-06 — só o canal daquela run
        recebe) E ao stream global via ``broadcast``, que ignora sockets de
        canal de run. Assim o canal de run não vaza eventos de outras runs em
        multi-run.
        """
        try:
            loop = asyncio.get_running_loop()
            run_id = envelope.get("run_id")
            if run_id:
                loop.create_task(ws_manager.send_to_run(run_id, envelope))
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
            # Lock: protege contra publishes concorrentes multi-thread.
            with self._mem_lock:
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
        if self._redis is not None:
            try:
                # Envelope do CANAL ganha origin (worker-id) para dedup no
                # forwarder; journal e broadcast local permanecem intactos.
                channel_envelope = {**envelope, "origin": WORKER_ID}
                await self._redis.publish("lf:events", json.dumps(channel_envelope))
            except Exception:
                logger.warning("Falha ao publicar evento no redis", exc_info=True)
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

    async def get_timeline(self, run_id: str, after_seq: int = 0, limit: int = 100) -> dict:
        """Timeline unificada da run (C5/M-02): eventos do journal + checkpoints.

        Intercala os dois streams (eventos da tabela ``events`` + checkpoints do
        LangGraph na thread canônica ``run-{id}``, ADR-0003) ordenado por
        timestamp. Cada item da timeline tem ``{seq, type, timestamp, node,
        data}`` — ``seq`` é a posição 1-based na lista MERGED; ``type`` é
        ``"event"`` ou ``"checkpoint"``; ``node`` vem do payload/metadata quando
        disponível; ``data`` é o payload do evento OU o checkpoint inteiro
        serializado (checkpoint_id, parent_checkpoint_id, type, metadata,
        checkpoint).

        ``after_seq``/``limit`` paginam a timeline merged e o retorno segue o
        padrão do backfill de events: ``{run_id, timeline, total_count,
        has_more, next_after_seq}``.
        """
        # Query 1: TODOS os eventos do journal (a paginação acontece pós-merge).
        events = await self.list_events(run_id, after_seq=0, limit=10**9)
        # Query 2: checkpoints LangGraph da thread canônica da run (em to_thread).
        checkpoints = await asyncio.to_thread(_load_checkpoints_for_thread, f"run-{run_id}")

        merged: list[dict] = []
        for env in events:
            merged.append(
                {
                    "type": "event",
                    "timestamp": env["timestamp"],
                    "node": env["payload"].get("node"),
                    "data": env["payload"],
                    "_sort": (env["timestamp"], 0, env["seq"]),
                }
            )
        for cp in checkpoints:
            ts = (cp["checkpoint"] or {}).get("ts") or ""
            merged.append(
                {
                    "type": "checkpoint",
                    "timestamp": ts,
                    "node": cp["metadata"].get("node"),
                    "data": cp,
                    "_sort": (ts, 1, cp["checkpoint_id"]),
                }
            )

        # Intercala por timestamp (eventos antes de checkpoints no mesmo instante)
        # e deduplica itens idênticos (type+timestamp+data), se houver.
        merged.sort(key=lambda item: item["_sort"])
        timeline: list[dict] = []
        seen: set[tuple] = set()
        for item in merged:
            dedup_key = (
                item["type"],
                item["timestamp"],
                json.dumps(item["data"], sort_keys=True, default=str),
            )
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            item.pop("_sort")
            timeline.append(item)

        for idx, item in enumerate(timeline, start=1):
            item["seq"] = idx

        total_count = len(timeline)
        page = [item for item in timeline if item["seq"] > after_seq][:limit]
        has_more = after_seq + len(page) < total_count
        next_after_seq = page[-1]["seq"] if page and has_more else None
        return {
            "run_id": run_id,
            "timeline": page,
            "total_count": total_count,
            "has_more": has_more,
            "next_after_seq": next_after_seq,
        }


event_bus = EventBus()
