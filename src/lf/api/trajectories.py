"""Rotas de trajetórias (checkpoints + export/import/fork) da ADE.

Consome ``TaskDispatcher.list_checkpoints()`` e ``create_async_checkpointer``
para ler/gravar checkpoints em ``.loopforge/trajectories.db``. O envelope
versionado produzido aqui é consumido pela Fase 3 (time-travel).
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class TrajectoryStep(BaseModel):
    node: str
    ts: str
    state_in: dict[str, Any] = Field(default_factory=dict)
    state_out: dict[str, Any] = Field(default_factory=dict)
    tokens: int = 0
    cost_usd: float = 0.0
    decision: str | None = None


class TrajectoryEnvelope(BaseModel):
    schema_version: str = "1.0"
    thread_id: str
    created_at: str
    steps: list[TrajectoryStep] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


trajectories_router = APIRouter(prefix="/api/v1/trajectories", tags=["Trajectories"])


def _trajectories_db() -> Path:
    """Caminho do banco de trajetórias resolvido em call-time.

    Resolve em call-time (não em import-time) para respeitar os.chdir()/
    monkeypatch.chdir() usados pelos testes e pela CLI em diretórios de
    trabalho arbitrários (mesmo padrão do TaskDispatcher).
    """
    return Path(".loopforge/trajectories.db").resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _list_thread_ids() -> list[str]:
    """Thread_ids únicos do banco de trajetórias (TaskDispatcher)."""
    from lf.orchestrator.task_dispatcher import TaskDispatcher

    return TaskDispatcher().list_checkpoints()


@trajectories_router.get("/{thread_id}/checkpoints")
def list_checkpoints(thread_id: str):
    """Lista os thread_ids do banco de trajetórias filtrados pelo segmento.

    Rota síncrona (def) porque ``TaskDispatcher.list_checkpoints()`` usa
    ``asyncio.run`` internamente — chamado de dentro de um async def o
    evento já estaria rodando e levantaria RuntimeError.
    """
    return [{"thread_id": t} for t in _list_thread_ids() if t == thread_id]


@trajectories_router.get("/{thread_id}/checkpoints/{checkpoint_id}")
async def get_checkpoint(thread_id: str, checkpoint_id: str):
    """Retorna o estado de um checkpoint específico da thread."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(_trajectories_db())
    try:
        await saver.setup()
        value = await saver.aget_tuple(
            {"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}}
        )
    finally:
        await saver.conn.close()
    if value is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} não encontrado")
    return {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
        "state": value.checkpoint.get("channel_values", {}),
    }


@trajectories_router.get("/{thread_id}/export")
def export_trajectory(thread_id: str):
    """Exporta a trajetória da thread como envelope versionado."""
    if thread_id not in _list_thread_ids():
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} não encontrada")
    # Envelope mínimo — enriquecido com steps/events na Fase 3 (time-travel)
    return TrajectoryEnvelope(thread_id=thread_id, created_at=_now())


@trajectories_router.post("/import", status_code=201)
def import_trajectory(envelope: TrajectoryEnvelope):
    """Importa um envelope criando a thread (409 se já existir; 422 se schema inválido)."""
    if envelope.schema_version != "1.0":
        raise HTTPException(status_code=422, detail="schema_version suportada: 1.0")
    if envelope.thread_id in _list_thread_ids():
        raise HTTPException(status_code=409, detail="Thread já existe; sem merge no V1")
    # Persistir envelope como artefato da trajetória (steps completos chegam
    # com o time-travel na Fase 3)
    meta = _trajectories_db().with_name("trajectory-imports.json")
    records = []
    if meta.exists():
        records = json.loads(meta.read_text())
    records.append(envelope.model_dump(mode="json"))
    meta.write_text(json.dumps(records, indent=2))
    return envelope


@trajectories_router.post("/{thread_id}/fork", status_code=201)
def fork_trajectory(thread_id: str):
    """Deriva uma nova thread com sufixo ``-fork-<ts>`` (sem copiar checkpoints no V1)."""
    if thread_id not in _list_thread_ids():
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} não encontrada")
    fork_id = f"{thread_id}-fork-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    return {"fork_thread_id": fork_id, "source_thread_id": thread_id}
