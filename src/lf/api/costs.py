"""Rotas de custo por run (M-08/M-09/M-10 da Fase A).

- ``GET /api/v1/runs/{id}/cost``: soma llm_costs do run, budget efetivo
  (fonte única ade.yaml + override) e ``budget_warning`` (percent >= 80%).
- ``POST /api/v1/runs/{id}/cost/override``: atualiza o budget efetivo do run
  (retomada de run pausada por budget com limite maior).

O ledger llm_costs é SQLite puro em ``.loopforge/telemetry.sqlite`` (escrito
pelo CostTracker em lf/pipeline/llm_factory.py) — por isso as rotas leem o
arquivo direto (resolvido em call-time, mesmo padrão do CostTracker), enquanto
a existência da run vem do ORM (session).
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from lf.api.auth import verify_authentication
from lf.api.database import get_session
from lf.api.models import PipelineRun
from lf.api.schemas import BudgetOverrideRequest, CostResponse
from lf.config.loader import load_budget_usd

costs_router = APIRouter(prefix="/api/v1", tags=["Costs"])

# Override de budget efetivo por run (run_id -> max_usd). Tabela SIMPLES em
# memória (decisão documentada): o objetivo é permitir retomar uma run pausada
# por budget com limite maior — o override é aplicado também ao CircuitBreaker
# do checkpoint (trajectories.db) para que o resume use o novo limite.
# Persistir em SQLite exigiria migração de schema no banco único (fora do
# escopo A6); para o fluxo pausa→override→resume em um processo (API/CLI) a
# memória é suficiente.
_BUDGET_OVERRIDES: dict[str, float] = {}


def get_budget_override(run_id: str) -> float | None:
    """Retorna o override ativo da run, se houver."""
    return _BUDGET_OVERRIDES.get(run_id)


def _telemetry_db() -> Path:
    """Caminho do telemetry.sqlite resolvido em call-time (monkeypatch.chdir-safe)."""
    return Path(".loopforge/telemetry.sqlite").resolve()


def _trajectories_db() -> Path:
    """Caminho do trajectories.db (checkpoints) resolvido em call-time."""
    return Path(".loopforge/trajectories.db").resolve()


def _sum_run_costs(run_id: str) -> tuple[float, bool]:
    """Soma cost_usd de llm_costs da run + flag se alguma linha é estimada.

    Retorna (0.0, False) silenciosamente se a tabela não existir (nenhuma
    chamada LLM registrada ainda).
    """
    import sqlite3

    db_path = _telemetry_db()
    if not db_path.exists():
        return 0.0, False
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_costs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            spent = float(row[0]) if row else 0.0
            row_est = conn.execute(
                "SELECT COUNT(*) FROM llm_costs WHERE run_id = ? AND estimated = 1",
                (run_id,),
            ).fetchone()
            estimated = bool(row_est and row_est[0] > 0)
            return spent, estimated
        finally:
            conn.close()
    except sqlite3.Error:
        return 0.0, False


async def _apply_override_to_checkpoint(run_id: str, thread_id: str, max_usd: float) -> bool:
    """Aplica o novo limite ao CircuitBreaker persistido no checkpoint da run.

    Permite que o resume re-execute o nó developer com o limite maior (M-10):
    sem isso o CB do estado continuaria com o limite antigo e a run pausaria
    de novo. Retorna False silenciosamente quando não há checkpoint/estado
    utilizável (ex.: run ainda não dispatchada) — o override em memória
    continua valendo para GET /cost.
    """
    db_path = _trajectories_db()
    if not db_path.exists():
        return False
    try:
        from lf.guardrails.circuit_breaker import CircuitBreaker
        from lf.pipeline.checkpointer import create_async_checkpointer
        from lf.pipeline.graph import build_graph

        saver = create_async_checkpointer(db_path)
        try:
            await saver.setup()
            graph = build_graph(checkpointer=saver)
            config = {"configurable": {"thread_id": thread_id}}
            snapshot = await graph.aget_state(config)
            if snapshot is None or not snapshot.values:
                return False
            cb_data = snapshot.values.get("circuit_breaker")
            if not isinstance(cb_data, dict):
                return False
            cb = CircuitBreaker.from_snapshot(cb_data)
            cb.max_total_cost = max_usd
            await graph.aupdate_state(config, {"circuit_breaker": cb.snapshot()})
            return True
        finally:
            await saver.conn.close()
    except Exception:
        return False


def _effective_max_usd(run_id: str) -> float:
    """Budget efetivo: override > ade.yaml (fonte única)."""
    override = get_budget_override(run_id)
    if override is not None:
        return override
    return load_budget_usd()


@costs_router.get("/runs/{run_id}/cost", response_model=CostResponse)
async def get_run_cost(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> CostResponse:
    """Custo acumulado + estado do budget da run (404 se a run não existe)."""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    spent, estimated = _sum_run_costs(run_id)
    max_usd = _effective_max_usd(run_id)
    percent_used = (spent / max_usd) if max_usd > 0 else 0.0
    budget_warning = percent_used >= 0.80  # M-10: aviso aos 80%

    return CostResponse(
        run_id=run_id,
        spent_usd=round(spent, 6),
        estimated=estimated,
        budget={
            "max_usd": max_usd,
            "percent_used": round(percent_used, 4),
        },
        budget_warning=budget_warning,
    )


@costs_router.post("/runs/{run_id}/cost/override", response_model=CostResponse)
async def override_run_budget(
    run_id: str,
    payload: BudgetOverrideRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> CostResponse:
    """Atualiza o budget efetivo da run (retoma run pausada com limite maior).

    Body ``{max_usd: float}`` ou vazio para usar ade.yaml. 404 se a run não
    existe; 422 se max_usd <= 0.
    """
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if payload is not None and payload.max_usd is not None:
        max_usd = payload.max_usd
    else:
        max_usd = load_budget_usd()

    _BUDGET_OVERRIDES[run_id] = max_usd

    thread_id = run.thread_id or f"run-{run.id}"
    # Aplica o novo limite ao CircuitBreaker do checkpoint (trajectories.db)
    # para que o resume re-execute o developer com o limite maior (M-10).
    await _apply_override_to_checkpoint(run_id, thread_id, max_usd)

    spent, estimated = _sum_run_costs(run_id)
    percent_used = (spent / max_usd) if max_usd > 0 else 0.0
    budget_warning = percent_used >= 0.80

    return CostResponse(
        run_id=run_id,
        spent_usd=round(spent, 6),
        estimated=estimated,
        budget={
            "max_usd": max_usd,
            "percent_used": round(percent_used, 4),
        },
        budget_warning=budget_warning,
    )
