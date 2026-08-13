"""Endpoint de artifacts por run — nó → output + tokens + estado da run.

Fonte dupla: último checkpoint LangGraph (trajectories.db — canais de
artefato do GraphState) + llm_costs/lessons (telemetry.sqlite). Padrão de
paths call-time e PRAGMA busy_timeout herdado de costs.py/trajectories.py.
"""

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.database import get_session
from lf.api.models import PipelineRun
from lf.api.schemas import (
    ArtifactLesson,
    ArtifactsResponse,
    ArtifactTokens,
    CircuitBreakerSnapshot,
    NodeArtifact,
)

artifacts_router = APIRouter(prefix="/api/v1", tags=["Artifacts"])

# Canais de artefato por nó canônico do DAG (ordem = ordem de exibição).
# security_report/devops_report são markdown (str) — renomeados com sufixo
# _md no output para não colidir com os canais estruturados homônimos
# security_review/devops_manifest (dicts).
NODE_CHANNELS: dict[str, tuple[str, ...]] = {
    "cpo": ("epic",),
    "pm": ("user_stories",),
    "tech_lead": ("tech_spec", "stack_rationale"),
    "test_writer": ("contract_tests",),
    "developer": ("code",),
    "qa": ("test_report",),
    "parallel_audit": ("security_review", "devops_manifest", "security_report", "devops_report"),
}

_MD_RENAMES = {"security_report": "security_report_md", "devops_report": "devops_report_md"}


def _trajectories_db() -> Path:
    """Caminho do banco de trajetórias resolvido em call-time."""
    return Path(".loopforge/trajectories.db").resolve()


def _telemetry_db() -> Path:
    """Caminho do telemetry.sqlite resolvido em call-time."""
    return Path(".loopforge/telemetry.sqlite").resolve()


def _node_tokens(run_id: str) -> list[ArtifactTokens]:
    """Tokens + custo LLM agregados por nó (llm_costs → GROUP BY node, model)."""
    db_path = _telemetry_db()
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            rows = conn.execute(
                "SELECT node, model, SUM(prompt_tokens), SUM(completion_tokens), "
                "SUM(cost_usd), MAX(estimated) FROM llm_costs "
                "WHERE run_id = ? GROUP BY node, model ORDER BY node",
                (run_id,),
            ).fetchall()
            return [
                ArtifactTokens(
                    node=str(row[0]),
                    model=str(row[1]) if row[1] else None,
                    prompt_tokens=int(row[2] or 0),
                    completion_tokens=int(row[3] or 0),
                    cost_usd=round(float(row[4] or 0.0), 6),
                    estimated=bool(row[5]),
                )
                for row in rows
            ]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


def _run_lessons(run_id: str) -> list[ArtifactLesson]:
    """Lições aprendidas da run (tabela lessons, mais recentes primeiro)."""
    db_path = _telemetry_db()
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            rows = conn.execute(
                "SELECT id, run_id, lesson_text, created_at FROM lessons WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
            return [
                ArtifactLesson(
                    id=int(row[0]),
                    run_id=str(row[1]),
                    lesson_text=str(row[2]),
                    created_at=float(row[3]),
                )
                for row in rows
            ]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


@artifacts_router.get("/runs/{run_id}/artifacts", response_model=ArtifactsResponse)
async def get_run_artifacts(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> ArtifactsResponse:
    """Artifacts por nó + tokens + estado de auditoria da run (404 se não existe)."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    from lf.pipeline.checkpointer import create_async_checkpointer

    node_artifacts: dict[str, NodeArtifact] = {}
    degraded = False
    degraded_reason: str | None = None
    circuit_breaker: CircuitBreakerSnapshot | None = None

    saver = None
    try:
        saver = create_async_checkpointer(_trajectories_db())
        await saver.setup()
        thread_id = run.thread_id or f"run-{run.id}"
        async with saver.conn.execute(
            "SELECT checkpoint_id FROM checkpoints WHERE thread_id = ? ORDER BY checkpoint_id DESC LIMIT 1",
            (thread_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is not None:
            value = await saver.aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_id": row[0]}})
            if value is not None:
                channels = value.checkpoint.get("channel_values", {}) or {}
                for node, keys in NODE_CHANNELS.items():
                    output = {k: channels[k] for k in keys if channels.get(k) not in (None, "")}
                    if output:
                        for src, dst in _MD_RENAMES.items():
                            if src in output:
                                output[dst] = output.pop(src)
                        node_artifacts[node] = NodeArtifact(output=output)
                degraded = bool(channels.get("degraded", False))
                degraded_reason = channels.get("degraded_reason")
                if not isinstance(degraded_reason, str):
                    degraded_reason = None
                cb = channels.get("circuit_breaker")
                if isinstance(cb, dict):
                    circuit_breaker = CircuitBreakerSnapshot(**cb)
    except Exception:
        # Checkpoint corrompido/indisponível (ex.: fields None do CB) → resposta
        # 200 com artifacts vazios em vez de 500 (padrão costs.py _node_cost_breakdown).
        node_artifacts = {}
        degraded = False
        degraded_reason = None
        circuit_breaker = None
    finally:
        if saver is not None:
            await saver.conn.close()

    return ArtifactsResponse(
        run_id=run_id,
        node_artifacts=node_artifacts,
        tokens=_node_tokens(run_id),
        degraded=degraded,
        degraded_reason=degraded_reason,
        circuit_breaker=circuit_breaker,
        lessons=_run_lessons(run_id),
    )
