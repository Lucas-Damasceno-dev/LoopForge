"""Testes da API de evals (pilar 5 — EvalsPanel da ADE).

Cobre:
- GET /api/v1/evals/summary: agregados de pipeline_runs + benchmark + ELO,
  com fallback a zeros quando banco/tabelas ausentes (telemetria nunca 500).
- GET /api/v1/evals/leaderboard: ranking de run_*.json (sucesso/duração),
  lista vazia com status quando não há dados, arquivos corrompidos ignorados.

Padrão endurecido de test_api_trajectories_fork_export: LF_API_TEST=1 +
init_db em tmp_path hermético; seeds escritos via sqlite3 puro em
.loopforge/telemetry.sqlite (mesmo schema do dispatcher/CostTracker).
"""

import json
import sqlite3
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


def _insert_pipeline_run(
    run_id: str,
    status: str,
    duration_seconds: float = 0.0,
    stack: str = "python",
) -> None:
    """Cria uma run em pipeline_runs (mesmo schema do dispatcher)."""
    db_path = Path(".loopforge/telemetry.sqlite").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS pipeline_runs (
                id VARCHAR(36) PRIMARY KEY, idea TEXT NOT NULL,
                stack VARCHAR(50) DEFAULT 'python', status VARCHAR(20) DEFAULT 'pending',
                current_node VARCHAR(50), logs TEXT, duration_seconds FLOAT DEFAULT 0.0,
                thread_id VARCHAR(50), parent_run_id VARCHAR(36),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            "INSERT OR REPLACE INTO pipeline_runs (id, idea, stack, status, duration_seconds) VALUES (?, ?, ?, ?, ?)",
            (run_id, f"idea-{run_id}", stack, status, duration_seconds),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_llm_costs(total_cost: float) -> None:
    """Insere uma linha única no ledger llm_costs com custo total dado."""
    db_path = Path(".loopforge/telemetry.sqlite").resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS llm_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL, completion_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                run_id TEXT, node TEXT, estimated INTEGER DEFAULT 0)"""
        )
        conn.execute(
            "INSERT INTO llm_costs (model, prompt_tokens, completion_tokens, cost_usd, run_id, node) "
            "VALUES ('mock', 0, 0, ?, 'run-1', 'developer')",
            (total_cost,),
        )
        conn.commit()
    finally:
        conn.close()


def _write_benchmark_run(
    run_id: str,
    *,
    stack: str = "python",
    success: bool = True,
    duration_seconds: float = 10.0,
    estimated_cost_usd: float = 0.5,
    timestamp: str = "2026-08-12T00:00:00+00:00",
) -> None:
    """Grava um run_*.json com a mesma shape do RunBenchmark.asdict()."""
    bdir = Path(".loopforge/benchmarks").resolve()
    bdir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "stack": stack,
        "idea": f"idea-{run_id}",
        "total_duration_seconds": duration_seconds,
        "estimated_cost_usd": estimated_cost_usd,
        "node_benchmarks": [],
        "success": success,
        "timestamp": timestamp,
    }
    (bdir / f"run_{run_id}.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _write_elo(current_elo: float) -> None:
    """Grava elo_history.json com o rating atual."""
    bdir = Path(".loopforge/benchmarks").resolve()
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "elo_history.json").write_text(
        json.dumps({"current_elo": current_elo, "history": []}, indent=2),
        encoding="utf-8",
    )


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    """Banco SQLite limpo em tmp_path para cada teste (LF_API_TEST=1)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()
    monkeypatch.delenv("LF_API_TEST", raising=False)


@pytest.mark.asyncio
async def test_summary_empty_db_returns_zeros():
    """Sem telemetria → 200 com zeros e status empty (nunca 500)."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_runs"] == 0
    assert body["pass_rate"] == 0.0
    assert body["avg_duration_seconds"] == 0.0
    assert body["total_cost_usd"] == 0.0
    assert body["benchmark_runs"] == 0
    assert body["avg_pass_rate"] == 0.0
    assert body["current_elo"] == 1200.0
    assert body["status"] == "empty"


@pytest.mark.asyncio
async def test_summary_with_pipeline_and_benchmark_data():
    """Dados de pipeline_runs + llm_costs + benchmark → métricas agregadas."""
    _insert_pipeline_run("run-1", "completed", duration_seconds=30.0)
    _insert_pipeline_run("run-2", "completed", duration_seconds=60.0)
    _insert_pipeline_run("run-3", "failed", duration_seconds=90.0)
    _insert_pipeline_run("run-4", "running", duration_seconds=0.0)
    _seed_llm_costs(4.25)
    _write_benchmark_run("b-1", success=True, duration_seconds=10.0)
    _write_benchmark_run("b-2", success=False, duration_seconds=25.0)
    _write_elo(1310.5)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/summary")
    assert resp.status_code == 200
    body = resp.json()
    # 4 runs totais; pass rate só entre concluídas: 2/3 ≈ 0.6667
    assert body["total_runs"] == 4
    assert body["pass_rate"] == pytest.approx(0.6667, abs=0.001)
    # duração média das concluídas com sucesso: (30+60)/2 = 45
    assert body["avg_duration_seconds"] == 45.0
    assert body["total_cost_usd"] == 4.25
    assert body["benchmark_runs"] == 2
    assert body["avg_pass_rate"] == 0.5
    assert body["current_elo"] == 1310.5
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_summary_missing_cost_table_keeps_run_metrics():
    """pipeline_runs existe mas llm_costs não → custo 0 sem derrubar o resto."""
    _insert_pipeline_run("run-1", "completed", duration_seconds=12.0)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_runs"] == 1
    assert body["pass_rate"] == 1.0
    assert body["total_cost_usd"] == 0.0
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_leaderboard_empty():
    """Sem benchmark → lista vazia com status empty."""
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["status"] == "empty"


@pytest.mark.asyncio
async def test_leaderboard_sorted_success_first_then_fastest():
    """Ranking: sucesso primeiro; entre iguais, mais rápido primeiro."""
    _write_benchmark_run(
        "slow-ok",
        success=True,
        duration_seconds=50.0,
        timestamp="2026-08-12T00:01:00+00:00",
    )
    _write_benchmark_run(
        "fast-ok",
        success=True,
        duration_seconds=10.0,
        timestamp="2026-08-12T00:00:00+00:00",
    )
    _write_benchmark_run(
        "fail",
        success=False,
        duration_seconds=5.0,
        timestamp="2026-08-12T00:02:00+00:00",
    )

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [e["run_id"] for e in body["entries"]] == ["fast-ok", "slow-ok", "fail"]
    first = body["entries"][0]
    assert first["stack"] == "python"
    assert first["success"] is True
    assert first["duration_seconds"] == 10.0
    assert first["estimated_cost_usd"] == 0.5
    assert first["timestamp"] == "2026-08-12T00:00:00+00:00"


@pytest.mark.asyncio
async def test_leaderboard_ignores_corrupt_files():
    """Arquivo corrompido não derruba a rota nem aparece no ranking."""
    bdir = Path(".loopforge/benchmarks").resolve()
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "run_corrupt.json").write_text("{not-json", encoding="utf-8")
    _write_benchmark_run("valid", success=True, duration_seconds=3.0)

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/evals/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert [e["run_id"] for e in body["entries"]] == ["valid"]
