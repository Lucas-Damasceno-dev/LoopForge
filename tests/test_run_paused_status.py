"""Teste M-10 (n2b): hard-stop de budget → run PAUSED via API (não completed/failed).

O n4 mudou o hard-stop do developer para PAUSA via ``interrupt()`` (a run não
falha; o checkpoint fica pendente). Este teste verifica o complemento M-10 no
``_run_pipeline``: a detecção de pausa via checkpoint (``next != []``) marca a
run como ``paused`` no DB — e o journal (M-06) registra ``run_updated`` com
status ``paused``.
"""
import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.config.loader import save_ade_config
from lf.config.schema import AdeBudget, AdeConfig


@pytest_asyncio.fixture(autouse=True)
async def setup_api(tmp_path, monkeypatch):
    """Banco API SQLite limpo em tmp_path (padrão de test_budget_pause_override.py)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_API_TEST", "1")
    monkeypatch.setenv("LF_API_REQUIRE_AUTH", "false")
    await init_db()
    yield
    await close_db()


def _write_ade_budget(tmp_path: Path, max_usd: float) -> None:
    """ade.yaml com budget baixo (fonte única M-08) no diretório de trabalho."""
    cfg_path = tmp_path / ".loopforge" / "ade.yaml"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    save_ade_config(AdeConfig(budget=AdeBudget(max_usd=max_usd)), cfg_path)


async def _next_nodes_of_thread(thread_id: str) -> list[str]:
    """Nós PENDENTES do checkpoint da thread (vazio = run terminou)."""
    from lf.pipeline.checkpointer import create_async_checkpointer
    from lf.pipeline.graph import build_graph

    saver = create_async_checkpointer(Path(".loopforge/trajectories.db"))
    try:
        await saver.setup()
        graph = build_graph(checkpointer=saver)
        snap = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return list(snap.next) if snap else []
    finally:
        await saver.conn.close()


async def _wait_terminal(client: AsyncClient, run_id: str, timeout: float = 30.0) -> str:
    """Poll GET /api/runs/{id} até a run sair de pending/running."""
    waited = 0.0
    status = "pending"
    while waited < timeout:
        status = (await client.get(f"/api/runs/{run_id}")).json()["status"]
        if status in ("completed", "failed", "paused"):
            return status
        await asyncio.sleep(0.2)
        waited += 0.2
    raise AssertionError(f"run {run_id} não terminou em {timeout}s (status: {status})")


@pytest.mark.asyncio
async def test_run_paused_status_via_api(tmp_path):
    """Run com budget estourado → GET /api/v1/runs/{id} mostra status ``paused``."""
    _write_ade_budget(tmp_path, 0.01)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/runs",
            json={"idea": "Hard-stop pause", "stack": "python", "mock_llm": True},
        )
        assert resp.status_code == 201
        run_id = resp.json()["id"]
        thread_id = f"run-{run_id}"

        status = await _wait_terminal(client, run_id)
        # M-10: pausa, NÃO completed/failed
        assert status == "paused", f"hard-stop deveria pausar a run, não {status!r}"

        # Checkpoint pendente no nó developer (run retomável)
        next_nodes = await _next_nodes_of_thread(thread_id)
        assert "developer" in next_nodes, f"checkpoint deveria estar pendente no developer: {next_nodes}"

        # Custo reflete o estouro + run pausada (wire do costs_router)
        cost = await client.get(f"/api/v1/runs/{run_id}/cost")
        assert cost.status_code == 200
        assert cost.json()["budget"]["max_usd"] == 0.01

        # Journal (M-06): run_updated com status paused está persistido
        events = (await client.get(f"/api/v1/runs/{run_id}/events")).json()["events"]
        updated_statuses = [
            e["payload"].get("status") for e in events if e["event"] == "run_updated"
        ]
        assert "paused" in updated_statuses, f"run_updated paused ausente: {updated_statuses}"
        # A run não emitiu terminal completed/failed no journal
        assert "completed" not in updated_statuses and "failed" not in updated_statuses
