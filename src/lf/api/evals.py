"""API de avaliações (evals) da telemetria de benchmarks (ADE — EvalsPanel).

Pilar 5 do BLUEPRINT: expõe métricas de benchmark/ELO via REST.

- ``GET /api/v1/evals/summary``: agregados de pipeline_runs (telemetry.sqlite)
  + arquivos de benchmark (.loopforge/benchmarks/) + rating ELO.
- ``GET /api/v1/evals/leaderboard``: ranking de runs de benchmark (mais
  rápidas primeiro), ou lista vazia com status quando não há dados.

Regra de ouro: telemetria NUNCA deve derrubar a API com 500. Toda leitura é
guardada em try/except e retorna zeros/listas vazias com ``status``
(``ok``/``empty``/``error``) — mesmo espírito dos endpoints genome/retro.

Leitura direta do SQLite em call-time (Path resolvido no request), mesmo
padrão de lf/api/costs.py: o ledger pipeline_runs/llm_costs vive em
``.loopforge/telemetry.sqlite`` e é escrito fora do ORM da API.
"""

import json
import sqlite3
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

evals_router = APIRouter(prefix="/api/v1/evals", tags=["Evals"])

# Status que representam conclusão com sucesso em pipeline_runs.
_SUCCESS_STATUSES = ("completed", "done")
# ELO inicial do LoopForge (mesmo default de lf/telemetry/benchmark.py).
_DEFAULT_ELO = 1200.0


class EvalsSummary(BaseModel):
    """Métricas agregadas de evals (runs, pass rate, duração, custo, ELO)."""

    total_runs: int = Field(..., description="Total de runs registradas em pipeline_runs")
    pass_rate: float = Field(
        ...,
        description="Taxa de sucesso (0.0–1.0) entre runs concluídas (completed/done vs failed)",
    )
    avg_duration_seconds: float = Field(
        ...,
        description="Duração média (s) das runs concluídas com sucesso",
    )
    total_cost_usd: float = Field(
        ...,
        description="Custo total (USD) acumulado no ledger llm_costs",
    )
    benchmark_runs: int = Field(..., description="Total de arquivos run_*.json em .loopforge/benchmarks/")
    avg_pass_rate: float = Field(
        ...,
        description="Taxa de sucesso média (0.0–1.0) das runs de benchmark",
    )
    current_elo: float = Field(..., description="Rating ELO atual do LoopForge")
    status: Literal["ok", "empty", "error"] = Field(..., description="Estado da leitura de telemetria")
    message: str = Field("", description="Mensagem descritiva (erros/estado vazio)")


class EvalsLeaderboardEntry(BaseModel):
    """Uma run de benchmark no ranking (fonte: run_*.json)."""

    run_id: str
    stack: str
    success: bool
    duration_seconds: float
    estimated_cost_usd: float
    timestamp: str


class EvalsLeaderboard(BaseModel):
    """Ranking de runs de benchmark (mais rápidas primeiro) + status da leitura."""

    entries: list[EvalsLeaderboardEntry] = Field(default_factory=list)
    status: Literal["ok", "empty", "error"] = Field(..., description="Estado da leitura de telemetria")
    message: str = Field("", description="Mensagem descritiva (erros/estado vazio)")


def _telemetry_db() -> Path:
    """Caminho do telemetry.sqlite resolvido em call-time (monkeypatch.chdir-safe)."""
    return Path(".loopforge/telemetry.sqlite").resolve()


def _benchmarks_dir() -> Path:
    """Diretório dos arquivos de benchmark (run_*.json + elo_history.json)."""
    return Path(".loopforge/benchmarks").resolve()


def _db_run_metrics() -> tuple[int, float, float]:
    """Métricas de pipeline_runs: (total_runs, pass_rate, avg_duration_seconds).

    Pass rate calculada apenas entre runs CONCLUÍDAS (completed/done vs failed):
    runs pending/running/paused não contam como falha. Duração média considera
    as concluídas com sucesso. Retorna zeros se a tabela/banco não existir.
    """
    db_path = _telemetry_db()
    if not db_path.exists():
        return 0, 0.0, 0.0
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            total = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()
            finished = conn.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE status IN ('completed', 'done')"
            ).fetchone()
            failed = conn.execute("SELECT COUNT(*) FROM pipeline_runs WHERE status = 'failed'").fetchone()
            avg_dur = conn.execute(
                "SELECT AVG(duration_seconds) FROM pipeline_runs WHERE status IN ('completed', 'done')"
            ).fetchone()
            total_runs = int(total[0]) if total else 0
            finished_runs = int(finished[0]) if finished else 0
            failed_runs = int(failed[0]) if failed else 0
            evaluated = finished_runs + failed_runs
            pass_rate = (finished_runs / evaluated) if evaluated > 0 else 0.0
            avg_duration = float(avg_dur[0]) if avg_dur and avg_dur[0] is not None else 0.0
            return total_runs, round(pass_rate, 4), round(avg_duration, 2)
        finally:
            conn.close()
    except sqlite3.Error:
        return 0, 0.0, 0.0


def _db_total_cost() -> float:
    """Custo total (USD) somado do ledger llm_costs.

    Query isolada da de pipeline_runs: a tabela llm_costs pode não existir em
    instalações sem nenhuma chamada LLM registrada, e isso não deve derrubar
    as métricas de runs.
    """
    db_path = _telemetry_db()
    if not db_path.exists():
        return 0.0
    try:
        conn = sqlite3.connect(str(db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout=5000")
            row = conn.execute("SELECT COALESCE(SUM(cost_usd), 0.0) FROM llm_costs").fetchone()
            return round(float(row[0]) if row else 0.0, 6)
        finally:
            conn.close()
    except sqlite3.Error:
        return 0.0


def _load_elo_rating() -> float:
    """Rating ELO atual de elo_history.json (1200.0 default em arquivo ausente/corrompido)."""
    elo_file = _benchmarks_dir() / "elo_history.json"
    if not elo_file.exists():
        return _DEFAULT_ELO
    try:
        with elo_file.open(encoding="utf-8") as f:
            data = json.load(f)
        return round(float(data.get("current_elo", _DEFAULT_ELO)), 1)
    except (OSError, ValueError, TypeError):
        return _DEFAULT_ELO


def _benchmark_metrics() -> tuple[int, float]:
    """Métricas dos arquivos run_*.json: (benchmark_runs, avg_pass_rate).

    Arquivos corrompidos contam no total de runs mas não como sucesso (mesma
    semântica de BenchmarkSuite.get_summary).
    """
    bdir = _benchmarks_dir()
    if not bdir.exists():
        return 0, 0.0
    try:
        files = sorted(f for f in bdir.iterdir() if f.name.startswith("run_") and f.suffix == ".json")
    except OSError:
        return 0, 0.0
    total = len(files)
    successful = 0
    for f in files:
        try:
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            if data.get("success", True):
                successful += 1
        except (OSError, ValueError, TypeError):
            continue
    avg_pass_rate = (successful / total) if total > 0 else 0.0
    return total, round(avg_pass_rate, 4)


def _leaderboard_entries() -> list[dict]:
    """Lê run_*.json e monta o ranking (sucesso primeiro, depois mais rápido).

    Ordenação: runs bem-sucedidas antes de falhas; entre as do mesmo grupo,
    as mais rápidas primeiro. Arquivos corrompidos são ignorados.
    """
    bdir = _benchmarks_dir()
    if not bdir.exists():
        return []
    try:
        files = sorted(f for f in bdir.iterdir() if f.name.startswith("run_") and f.suffix == ".json")
    except OSError:
        return []
    entries: list[dict] = []
    for f in files:
        try:
            with f.open(encoding="utf-8") as fh:
                data = json.load(fh)
            entries.append(
                {
                    "run_id": str(data.get("run_id", f.stem.removeprefix("run_"))),
                    "stack": str(data.get("stack", "python")),
                    "success": bool(data.get("success", True)),
                    "duration_seconds": round(float(data.get("total_duration_seconds", 0.0)), 2),
                    "estimated_cost_usd": round(float(data.get("estimated_cost_usd", 0.0)), 6),
                    "timestamp": str(data.get("timestamp", "")),
                }
            )
        except (OSError, ValueError, TypeError):
            continue
    entries.sort(key=lambda e: (not e["success"], e["duration_seconds"]))
    return entries


@evals_router.get("/summary", response_model=EvalsSummary)
async def get_evals_summary() -> EvalsSummary:
    """Resumo agregado de evals (runs, pass rate, duração, custo, ELO)."""
    try:
        total_runs, pass_rate, avg_duration = _db_run_metrics()
        total_cost = _db_total_cost()
        benchmark_runs, avg_pass_rate = _benchmark_metrics()
        current_elo = _load_elo_rating()
        status = "ok" if (total_runs > 0 or benchmark_runs > 0) else "empty"
        return EvalsSummary(
            total_runs=total_runs,
            pass_rate=pass_rate,
            avg_duration_seconds=avg_duration,
            total_cost_usd=total_cost,
            benchmark_runs=benchmark_runs,
            avg_pass_rate=avg_pass_rate,
            current_elo=current_elo,
            status=status,
        )
    except Exception as e:  # pragma: no cover — guarda defensiva, rotas internas já tratam erros
        return EvalsSummary(
            total_runs=0,
            pass_rate=0.0,
            avg_duration_seconds=0.0,
            total_cost_usd=0.0,
            benchmark_runs=0,
            avg_pass_rate=0.0,
            current_elo=_DEFAULT_ELO,
            status="error",
            message=f"Falha ao agregar telemetria de evals: {e}",
        )


@evals_router.get("/leaderboard", response_model=EvalsLeaderboard)
async def get_evals_leaderboard() -> EvalsLeaderboard:
    """Ranking de runs de benchmark (sucesso primeiro, mais rápidas primeiro)."""
    try:
        entries = _leaderboard_entries()
        status = "ok" if entries else "empty"
        return EvalsLeaderboard(entries=entries, status=status)
    except Exception as e:  # pragma: no cover — guarda defensiva, rotas internas já tratam erros
        return EvalsLeaderboard(
            entries=[],
            status="error",
            message=f"Falha ao carregar leaderboard de evals: {e}",
        )
