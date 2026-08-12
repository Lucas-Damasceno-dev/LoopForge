"""Rotas de trajetórias (checkpoints + export/import/fork) da ADE.

Implementa os contratos da Fase 1:

- ``GET /{thread_id}/checkpoints``: thread_ids do banco de trajetórias.
- ``GET /{thread_id}/checkpoints/{checkpoint_id}``: estado de um checkpoint.
- ``POST /export/{run_id}``: export enriquecido (M-14) — checkpoints
  serializados, steps por nó, eventos do journal e custos do ledger.
- ``GET /{thread_id}/export``: alias compat do export (envelope do thread).
- ``POST /import``: materializa um payload de export na thread (M-14).
- ``POST /{thread_id}/fork``: fork REAL (M-13) — copia os checkpoint tuples
  da thread origem para ``run-{fork_uuid}``, cria a run filha em
  ``pipeline_runs`` e publica o evento ``fork_created``.

O checkpointer é o ``AsyncSqliteSaver`` do langgraph-checkpoint-sqlite 3.1.0
em ``.loopforge/trajectories.db`` (schema: tabelas ``checkpoints`` com as
colunas thread_id/checkpoint_ns/checkpoint_id/parent_checkpoint_id/type/
checkpoint/metadata e ``writes``). O fork copia as linhas byte-a-byte; o
export desserializa via ``saver.serde`` (JsonPlusSerializer, tag msgpack) e o
import re-serializa o estado JSON de volta para o formato do saver.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from lf.api.auth import verify_authentication
from lf.api.events import event_bus

logger = logging.getLogger(__name__)


class ExportCheckpoint(BaseModel):
    """Checkpoint serializado para o export (M-14)."""

    checkpoint_id: str
    parent_checkpoint_id: str | None = None
    checkpoint_ns: str = ""
    ts: str | None = None
    step: int | None = None
    node: str | None = None
    state: dict[str, Any] | None = None
    state_summary: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrajectoryExport(BaseModel):
    """Payload do export enriquecido (M-14) — aceito pelo POST /import."""

    schema_version: str = "1.1"
    run_id: str
    thread_id: str
    exported_at: str
    idea: str = ""
    checkpoints: list[ExportCheckpoint] = Field(default_factory=list)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)
    costs: dict[str, Any] = Field(default_factory=dict)


trajectories_router = APIRouter(
    prefix="/api/v1/trajectories",
    tags=["Trajectories"],
    dependencies=[Depends(verify_authentication)],  # M-03: auth em todas as rotas
)

# Colunas do schema real do AsyncSqliteSaver 3.1.0 (inspecionado na lib):
# checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
# type, checkpoint, metadata) e writes (thread_id, checkpoint_ns,
# checkpoint_id, task_id, idx, channel, type, value).
_CHECKPOINT_COLS = "thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata"
_WRITE_COLS = "thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value"

# Chaves sensíveis omitidas do resumo de estado não-serializável (M-14).
_SENSITIVE_KEYS = ("password", "token", "secret", "api_key", "apikey")


def _trajectories_db() -> Path:
    """Caminho do banco de trajetórias resolvido em call-time.

    Resolve em call-time (não em import-time) para respeitar os.chdir()/
    monkeypatch.chdir() usados pelos testes e pela CLI em diretórios de
    trabalho arbitrários (mesmo padrão do TaskDispatcher).
    """
    return Path(".loopforge/trajectories.db").resolve()


def _telemetry_db() -> Path:
    """Caminho do banco único de telemetria resolvido em call-time."""
    return Path(".loopforge/telemetry.sqlite").resolve()


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _list_thread_ids() -> list[str]:
    """Thread_ids únicos do banco de trajetórias (TaskDispatcher)."""
    from lf.orchestrator.task_dispatcher import TaskDispatcher

    return TaskDispatcher().list_checkpoints()


# ─── Helpers do saver (AsyncSqliteSaver 3.1.0) ───────────────────────────


async def _thread_exists(saver, thread_id: str) -> bool:
    """True se a thread tem pelo menos um checkpoint no trajectories.db."""
    async with saver.conn.execute("SELECT 1 FROM checkpoints WHERE thread_id = ? LIMIT 1", (thread_id,)) as cur:
        return await cur.fetchone() is not None


async def _latest_checkpoint_id(saver, thread_id: str) -> str | None:
    """Último checkpoint_id da thread (ordem DESC do saver = head)."""
    async with saver.conn.execute(
        "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1",
        (thread_id,),
    ) as cur:
        row = await cur.fetchone()
    return row[0] if row else None


async def _copy_thread(saver, src_thread: str, dst_thread: str) -> int:
    """Copia checkpoints e writes da thread origem byte-a-byte para a nova.

    INSERT ... SELECT preserva todas as colunas do schema 3.1.0 (inclusive
    parent_checkpoint_id/type/blob), evitando perda de fidelidade na
    re-serialização dos blobs msgpack.
    """
    async with saver.conn.cursor() as cur:
        await cur.execute(
            f"INSERT INTO checkpoints ({_CHECKPOINT_COLS}) "
            f"SELECT ?, checkpoint_ns, checkpoint_id, parent_checkpoint_id, "
            f"type, checkpoint, metadata FROM checkpoints WHERE thread_id = ?",
            (dst_thread, src_thread),
        )
        # rowcount deve ser lido após o primeiro execute: o INSERT em `writes`
        # pode inserir 0 linhas (thread sem pending writes) e sobrescreveria
        # o contador com 0.
        copied = cur.rowcount
        await cur.execute(
            f"INSERT INTO writes ({_WRITE_COLS}) "
            f"SELECT ?, checkpoint_ns, checkpoint_id, task_id, idx, channel, "
            f"type, value FROM writes WHERE thread_id = ?",
            (dst_thread, src_thread),
        )
        await saver.conn.commit()
    return copied


def _state_to_json(state: dict) -> tuple[dict | None, str | None]:
    """Serializa o estado completo para JSON se possível; senão resumo seguro.

    Retorna ``(state_json, None)`` quando serializável (M-14: estado completo,
    NÃO máscara) ou ``(None, resumo)`` com campos sensíveis omitidos quando a
    serialização falha.
    """
    try:
        return json.loads(json.dumps(state, default=str)), None
    except (TypeError, ValueError):
        masked = {k: ("<redacted>" if any(s in k.lower() for s in _SENSITIVE_KEYS) else v) for k, v in state.items()}
        summary = json.dumps(masked, default=str, ensure_ascii=False)
        return None, summary[:2000]


async def _serialize_checkpoints(saver, thread_id: str) -> list[dict]:
    """Checkpoints da thread em ordem cronológica (estado completo em JSON)."""
    tuples = []
    async for item in saver.alist({"configurable": {"thread_id": thread_id}}):
        tuples.append(item)
    entries = []
    for item in reversed(tuples):  # alist é DESC (head primeiro) → cronológico
        meta = item.metadata or {}
        cp = item.checkpoint or {}
        cfg = (item.config or {}).get("configurable", {})
        state = cp.get("channel_values") or {}
        state_json, state_summary = _state_to_json(state)
        parent_cfg = (item.parent_config or {}).get("configurable", {}) if item.parent_config else {}
        writes = meta.get("writes") or {}
        node = next(iter(writes.keys())) if isinstance(writes, dict) and writes else None
        entries.append(
            ExportCheckpoint(
                checkpoint_id=cfg.get("checkpoint_id"),
                parent_checkpoint_id=parent_cfg.get("checkpoint_id"),
                checkpoint_ns=cfg.get("checkpoint_ns", ""),
                ts=cp.get("ts"),
                step=meta.get("step"),
                node=node,
                state=state_json,
                state_summary=state_summary,
                metadata=meta,
            ).model_dump()
        )
    return entries


async def _derive_steps(saver, thread_id: str) -> list[dict]:
    """Steps por nó derivados dos checkpoints (step/metadata + node)."""
    tuples = []
    async for item in saver.alist({"configurable": {"thread_id": thread_id}}):
        tuples.append(item)
    steps = []
    for item in reversed(tuples):
        meta = item.metadata or {}
        cp = item.checkpoint or {}
        cfg = (item.config or {}).get("configurable", {})
        writes = meta.get("writes") or {}
        node = (
            next(iter(writes.keys()))
            if isinstance(writes, dict) and writes
            else (cp.get("channel_values") or {}).get("next_agent")
        )
        steps.append(
            {
                "checkpoint_id": cfg.get("checkpoint_id"),
                "node": node,
                "step": meta.get("step"),
                "ts": cp.get("ts"),
            }
        )
    return steps


async def _materialize_checkpoints(saver, thread_id: str, checkpoints: list[dict]) -> int:
    """Recria os checkpoint tuples na thread a partir do payload de export."""
    count = 0
    for entry in checkpoints:
        state = entry.get("state")
        if not isinstance(state, dict):
            state = {}
        rebuilt = {
            "id": entry["checkpoint_id"],
            "v": 1,
            "ts": entry.get("ts") or _now(),
            "channel_values": state,
        }
        type_, blob = saver.serde.dumps_typed(rebuilt)
        meta = dict(entry.get("metadata") or {})
        meta.setdefault("source", "import")
        meta.setdefault("step", entry.get("step") or 0)
        serialized_meta = json.dumps(meta, ensure_ascii=False).encode("utf-8", "ignore")
        await saver.conn.execute(
            "INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_ns, "
            "checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                thread_id,
                entry.get("checkpoint_ns") or "",
                entry["checkpoint_id"],
                entry.get("parent_checkpoint_id"),
                type_,
                blob,
                serialized_meta,
            ),
        )
        count += 1
    await saver.conn.commit()
    return count


# ─── Helpers de ledger/telemetria (escrita direta, sem chamar o dispatcher) ──


def _read_origin_run(run_id: str) -> tuple[str, str]:
    """Idea/stack da run origem em pipeline_runs ("" / "python" se ausente)."""
    db_path = _telemetry_db()
    if not db_path.exists():
        return "", "python"
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            row = conn.execute("SELECT idea, stack FROM pipeline_runs WHERE id = ? LIMIT 1", (run_id,)).fetchone()
            if row:
                return (row[0] or ""), (row[1] or "python")
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return "", "python"


def _upsert_pipeline_run_direct(
    run_id: str,
    status: str,
    idea: str,
    stack: str,
    thread_id: str,
    parent_run_id: str | None = None,
) -> None:
    """Escrita direta em pipeline_runs (espelha task_dispatcher._upsert_pipeline_run).

    Implementação equivalente local (o dispatcher é canônico mas NÃO pode ser
    chamado aqui por design da ADE). Telemetria: nunca derruba a pipeline
    (try/except + logger.warning).
    """
    try:
        db_path = _telemetry_db()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id VARCHAR(36) PRIMARY KEY,
                    idea TEXT NOT NULL,
                    stack VARCHAR(50) DEFAULT 'python',
                    status VARCHAR(20) DEFAULT 'pending',
                    current_node VARCHAR(50),
                    logs TEXT,
                    duration_seconds FLOAT DEFAULT 0.0,
                    thread_id VARCHAR(50),
                    parent_run_id VARCHAR(36),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
            conn.execute(
                """
                INSERT INTO pipeline_runs
                    (id, idea, stack, status, duration_seconds, thread_id,
                     parent_run_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    thread_id = excluded.thread_id,
                    parent_run_id = excluded.parent_run_id,
                    updated_at = excluded.updated_at,
                    idea = CASE WHEN excluded.idea IS NOT NULL
                                THEN excluded.idea ELSE pipeline_runs.idea END,
                    stack = CASE WHEN excluded.stack IS NOT NULL
                                 THEN excluded.stack ELSE pipeline_runs.stack END
                """,
                (
                    run_id,
                    idea or "",
                    stack or "python",
                    status,
                    0.0,
                    thread_id,
                    parent_run_id,
                    now,
                    now,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Falha ao gravar pipeline_runs (run %s): %s", run_id, exc)


def _load_costs(run_id: str) -> dict:
    """Custos da run no ledger llm_costs (soma + linhas) — zero se ausente."""
    db_path = _telemetry_db()
    if not db_path.exists():
        return {"total_usd": 0.0, "estimated": False, "rows": []}
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            rows = conn.execute(
                "SELECT model, prompt_tokens, completion_tokens, cost_usd, node, "
                "estimated, created_at FROM llm_costs WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
            total = sum(float(r[3] or 0.0) for r in rows)
            return {
                "total_usd": round(total, 6),
                "estimated": bool(any(r[5] for r in rows)),
                "rows": [
                    {
                        "model": r[0],
                        "prompt_tokens": r[1],
                        "completion_tokens": r[2],
                        "cost_usd": r[3],
                        "node": r[4],
                        "estimated": bool(r[5]),
                        "created_at": r[6],
                    }
                    for r in rows
                ],
            }
        finally:
            conn.close()
    except sqlite3.Error:
        return {"total_usd": 0.0, "estimated": False, "rows": []}


async def _build_export(run_id: str, thread_id: str) -> dict:
    """Monta o payload do export enriquecido (checkpoints + steps + events + costs)."""
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(_trajectories_db())
    try:
        await saver.setup()
        if not await _thread_exists(saver, thread_id):
            raise HTTPException(status_code=404, detail=f"Run {run_id} não encontrada (sem trajetória)")
        checkpoints = await _serialize_checkpoints(saver, thread_id)
        steps = await _derive_steps(saver, thread_id)
    finally:
        await saver.conn.close()

    idea, _ = _read_origin_run(run_id)
    events = await event_bus.list_events(run_id)
    costs = _load_costs(run_id)
    return TrajectoryExport.model_validate(
        {
            "schema_version": "1.1",
            "run_id": run_id,
            "thread_id": thread_id,
            "exported_at": _now(),
            "idea": idea,
            "checkpoints": checkpoints,
            "steps": steps,
            "events": events,
            "costs": costs,
        }
    ).model_dump()


# ─── Rotas ────────────────────────────────────────────────────────────────


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
        value = await saver.aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_id": checkpoint_id}})
    finally:
        await saver.conn.close()
    if value is None:
        raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} não encontrado")
    return {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
        "state": value.checkpoint.get("channel_values", {}),
    }


@trajectories_router.post("/export/{run_id}")
async def export_trajectory(run_id: str):
    """Export enriquecido da run (M-14): thread canônica ``run-{run_id}`` (ADR-0003)."""
    return await _build_export(run_id, f"run-{run_id}")


@trajectories_router.get("/{thread_id}/export")
async def export_trajectory_compat(thread_id: str):
    """Alias compat do export por thread (GET legado — mesmo payload enriquecido)."""
    run_id = thread_id[4:] if thread_id.startswith("run-") else thread_id
    return await _build_export(run_id, thread_id)


def _validate_import(payload: Any) -> None:
    """Valida a estrutura do payload de import (422 com mensagem PT)."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload de import inválido: objeto JSON esperado")
    if payload.get("schema_version") != "1.1":
        raise HTTPException(status_code=422, detail="schema_version suportada: 1.1")
    if not isinstance(payload.get("run_id"), str) or not payload["run_id"]:
        raise HTTPException(status_code=422, detail="run_id é obrigatório (string não vazia)")
    if not isinstance(payload.get("thread_id"), str) or not payload["thread_id"]:
        raise HTTPException(status_code=422, detail="thread_id é obrigatório (string não vazia)")
    cps = payload.get("checkpoints")
    if not isinstance(cps, list):
        raise HTTPException(status_code=422, detail="checkpoints deve ser uma lista")
    for i, cp in enumerate(cps):
        if not isinstance(cp, dict) or not isinstance(cp.get("checkpoint_id"), str) or not cp["checkpoint_id"]:
            raise HTTPException(status_code=422, detail=f"checkpoints[{i}]: checkpoint_id é obrigatório")


@trajectories_router.post("/import", status_code=201)
async def import_trajectory(payload: dict):
    """Importa um payload de export materializando os checkpoints na thread (M-14).

    422 se a estrutura for inválida; 409 se a thread já existe (sem merge no
    V1); 201 ``{run_id, thread_id, checkpoints_imported}`` após materializar
    os checkpoint tuples e registrar a PipelineRun (status='queued').
    """
    _validate_import(payload)
    thread_id = payload["thread_id"]
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(_trajectories_db())
    try:
        await saver.setup()
        if await _thread_exists(saver, thread_id):
            raise HTTPException(status_code=409, detail="Thread já existe; sem merge no V1")
        count = await _materialize_checkpoints(saver, thread_id, payload["checkpoints"])
    finally:
        await saver.conn.close()

    _upsert_pipeline_run_direct(
        run_id=payload["run_id"],
        status="queued",
        idea=payload.get("idea") or "",
        stack="python",
        thread_id=thread_id,
    )
    return {
        "run_id": payload["run_id"],
        "thread_id": thread_id,
        "checkpoints_imported": count,
    }


@trajectories_router.post("/{thread_id}/fork", status_code=201)
async def fork_trajectory(thread_id: str):
    """Fork REAL (M-13): deriva uma thread nova copiando os checkpoints da origem.

    1. 404 se a run/thread origem não existe no trajectories.db.
    2. 409 se não há checkpoint copiável.
    3. Copia todos os checkpoint tuples (checkpoints + writes) para a thread
       nova ``run-{fork_uuid}`` preservando ids/chaves/metadados.
    4. Cria a PipelineRun filha (status='queued', parent_run_id, idea herdada).
    5. Publica o evento ``fork_created`` no EventBus (journal + broadcast).
    """
    from lf.pipeline.checkpointer import create_async_checkpointer

    saver = create_async_checkpointer(_trajectories_db())
    try:
        await saver.setup()
        if not await _thread_exists(saver, thread_id):
            raise HTTPException(status_code=404, detail=f"Run {thread_id} não encontrada (sem trajetória)")
        head = await _latest_checkpoint_id(saver, thread_id)
        if head is None:
            raise HTTPException(status_code=409, detail="Nenhum checkpoint copiável na thread de origem")

        fork_uuid = str(uuid.uuid4())
        new_thread = f"run-{fork_uuid}"
        copied = await _copy_thread(saver, thread_id, new_thread)
        if copied == 0:
            raise HTTPException(status_code=409, detail="Nenhum checkpoint copiável na thread de origem")
    finally:
        await saver.conn.close()

    # run_id da origem: thread canônica 'run-{id}' → id; senão a própria thread.
    origin_run_id = thread_id[4:] if thread_id.startswith("run-") else thread_id
    idea, stack = _read_origin_run(origin_run_id)
    _upsert_pipeline_run_direct(
        run_id=fork_uuid,
        status="queued",
        idea=idea,
        stack=stack,
        thread_id=new_thread,
        parent_run_id=origin_run_id,
    )
    await event_bus.publish(
        fork_uuid,
        "fork_created",
        {
            "parent_run_id": origin_run_id,
            "fork_run_id": fork_uuid,
            "checkpoint_id": head,
        },
    )
    return {
        "fork_run_id": fork_uuid,
        "thread_id": new_thread,
        "checkpoint_id": head,
    }
