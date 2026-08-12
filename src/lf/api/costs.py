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

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import DateTime, Float, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from lf.api import database
from lf.api.auth import verify_authentication
from lf.api.database import Base, get_session
from lf.api.models import PipelineRun
from lf.api.schemas import BudgetOverrideRequest, CostBudget, CostNode, CostResponse
from lf.config.loader import load_budget_usd

costs_router = APIRouter(prefix="/api/v1", tags=["Costs"])


def _now_utc() -> datetime:
    return datetime.now(UTC)


class BudgetOverride(Base):
    """Modelo ORM da tabela 'budget_overrides' — override de budget por run.

    Persistido no Banco Único da API (database.py): o override sobrevive a
    restart do servidor. O antigo dict em memória (_BUDGET_OVERRIDES) era
    perdido no restart e a run pausada por budget perdia o novo limite. PK =
    run_id (1 linha por run; POST /cost/override faz upsert).
    """

    __tablename__ = "budget_overrides"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    budget_usd: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), default="api")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


async def get_budget_override(run_id: str, session: AsyncSession | None = None) -> float | None:
    """Retorna o override persistido da run, se houver.

    Consulta a tabela ``budget_overrides`` do Banco Único da API
    (telemetry.sqlite; test_api.sqlite em LF_API_TEST). Com ``session`` injetada
    (endpoints) usa a sessão da request; sem ela abre sessão própria via
    ``session_factory`` (callers fora de request). Sem DB inicializado → None
    (nenhum override ativo).
    """
    if session is None:
        if database.session_factory is None:
            return None
        async with database.session_factory() as s:
            row = await s.get(BudgetOverride, run_id)
            return float(row.budget_usd) if row else None
    row = await session.get(BudgetOverride, run_id)
    return float(row.budget_usd) if row else None


async def set_budget_override(
    run_id: str,
    budget_usd: float,
    source: str = "api",
    session: AsyncSession | None = None,
) -> None:
    """Upsert do override da run em ``budget_overrides`` (persistente pós-restart).

    Cria a linha se não existir; atualiza ``budget_usd``/``source`` e o
    ``updated_at`` (onupdate) caso já exista. Com ``session`` injetada commit
    na sessão da request; sem ela, sessão própria via session_factory.
    """

    async def _upsert(s: AsyncSession) -> None:
        row = await s.get(BudgetOverride, run_id)
        if row is None:
            s.add(BudgetOverride(run_id=run_id, budget_usd=budget_usd, source=source))
        else:
            row.budget_usd = budget_usd
            row.source = source
        await s.commit()

    if session is not None:
        await _upsert(session)
    elif database.session_factory is not None:
        async with database.session_factory() as s:
            await _upsert(s)


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


def _node_cost_breakdown(run_id: str) -> list[CostNode]:
    """Custo agregado por nó da run (D1/Fase D): base dos chips da UI.

    Segunda query dedicada (não funde com _sum_run_costs): o total já tem
    semântica de COALESCE 0 e é SQLite barato. ``estimated`` por nó = true se
    QUALQUER linha do nó é estimada. Retorna [] se a tabela não existir.
    """
    import sqlite3

    db_path = _telemetry_db()
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            rows = conn.execute(
                "SELECT node, SUM(cost_usd), MAX(estimated) FROM llm_costs "
                "WHERE run_id = ? GROUP BY node ORDER BY node",
                (run_id,),
            ).fetchall()
            return [
                CostNode(
                    node=str(row[0]),
                    spent_usd=round(float(row[1] or 0.0), 6),
                    estimated=bool(row[2]),
                )
                for row in rows
            ]
        finally:
            conn.close()
    except sqlite3.Error:
        return []


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


async def _effective_max_usd(run_id: str, session: AsyncSession | None = None) -> float:
    """Budget efetivo: override persistido > ade.yaml (fonte única M-08)."""
    override = await get_budget_override(run_id, session)
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
    max_usd = await _effective_max_usd(run_id, session)
    percent_used = (spent / max_usd) if max_usd > 0 else 0.0
    budget_warning = percent_used >= 0.80  # M-10: aviso aos 80%

    return CostResponse(
        run_id=run_id,
        spent_usd=round(spent, 6),
        estimated=estimated,
        budget=CostBudget(
            max_usd=max_usd,
            percent_used=round(percent_used, 4),
        ),
        budget_warning=budget_warning,
        nodes=_node_cost_breakdown(run_id),
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
        budget=CostBudget(
            max_usd=max_usd,
            percent_used=round(percent_used, 4),
        ),
        budget_warning=budget_warning,
        nodes=_node_cost_breakdown(run_id),
    )
