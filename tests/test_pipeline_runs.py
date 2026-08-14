"""Testes da integração runs × pipelines (S3 T5): pipeline_id + snapshot imutável.

Fixtures no padrão test_api.py/test_memory_api.py. O executor (TaskDispatcher)
roda em background — testes com execução usam polling até status terminal.
"""

import asyncio
import contextlib
import os
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db


def _pipeline_payload(name: str = "flow", agent_id: str = "developer") -> dict:
    """Pipeline válida minimal: input → agent → output."""
    return {
        "name": name,
        "description": "test pipeline",
        "nodes": [
            {"id": "n1", "type": "input"},
            {"id": "n2", "type": "agent", "agent_id": agent_id},
            {"id": "n3", "type": "output"},
        ],
        "edges": [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
        ],
    }


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco SQLite limpo por teste (padrão test_api.py)."""
    from lf.api.database import Base, engine

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    db_file = ".loopforge/test_api.sqlite"
    if os.path.exists(db_file):
        with contextlib.suppress(Exception):
            os.remove(db_file)
    await init_db()
    if engine is not None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest_asyncio.fixture
async def client():
    """Cliente HTTP async."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _wait_terminal(client: AsyncClient, run_id: str, timeout: float = 60.0) -> dict:
    """Aguarda a run atingir status terminal (completed/failed/done)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(f"/api/v1/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        if data["status"] in ("completed", "failed", "done"):
            return data
        await asyncio.sleep(0.4)
    raise AssertionError(f"run {run_id} não terminou em {timeout}s")


async def _create_pipeline(client: AsyncClient, payload: dict) -> str:
    resp = await client.post("/api/v1/pipelines", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_run_sem_pipeline_id_comportamento_atual(client: AsyncClient):
    """POST /api/v1/runs sem pipeline_id → 201, pipeline_id None, snapshot NULL."""
    resp = await client.post("/api/v1/runs", json={"idea": "Run default"})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["pipeline_id"] is None
    assert data["pipeline_name"] is None

    from lf.api.database import session_factory
    from lf.api.models import PipelineRun

    async with session_factory() as session:
        run = await session.get(PipelineRun, data["id"])
        assert run is not None
        assert run.pipeline_id is None
        assert run.pipeline_snapshot is None


@pytest.mark.asyncio
async def test_run_pipeline_id_inexistente_404(client: AsyncClient):
    """POST /api/v1/runs com pipeline_id inexistente → 404 'Pipeline not found'."""
    resp = await client.post("/api/v1/runs", json={"idea": "X", "pipeline_id": "nao-existe"})
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "Pipeline not found"


@pytest.mark.asyncio
async def test_run_pipeline_invalida_422(client: AsyncClient):
    """Pipeline salva porém semanticamente inválida → run 422 'pipeline invalid: ...'."""
    payload = {
        "name": "quebrada",
        "nodes": [
            {"id": "n1", "type": "input"},
            {"id": "n3", "type": "output"},
        ],
        "edges": [{"source": "n1", "target": "ghost"}],
    }
    pipeline_id = await _create_pipeline(client, payload)

    resp = await client.post("/api/v1/runs", json={"idea": "X", "pipeline_id": pipeline_id})
    assert resp.status_code == 422, resp.text
    assert resp.json()["detail"].startswith("pipeline invalid")


@pytest.mark.asyncio
async def test_run_pipeline_valida_snapshot_persistido(client: AsyncClient):
    """Run com pipeline válida: 201 + pipeline_id/pipeline_name + snapshot no DB."""
    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="meu-flow"))

    resp = await client.post("/api/v1/runs", json={"idea": "com pipeline", "pipeline_id": pipeline_id})
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["pipeline_id"] == pipeline_id
    assert data["pipeline_name"] == "meu-flow"

    from lf.api.database import session_factory
    from lf.api.models import PipelineRun

    async with session_factory() as session:
        run = await session.get(PipelineRun, data["id"])
        assert run is not None
        assert run.pipeline_id == pipeline_id
        assert run.pipeline_snapshot is not None
        assert run.pipeline_snapshot["name"] == "meu-flow"
        assert len(run.pipeline_snapshot["nodes"]) == 3
        assert len(run.pipeline_snapshot["edges"]) == 2


@pytest.mark.asyncio
async def test_get_run_inclui_pipeline_name(client: AsyncClient):
    """GET run única e lista incluem pipeline_name."""
    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="flow-nome"))
    resp = await client.post("/api/v1/runs", json={"idea": "X", "pipeline_id": pipeline_id})
    run_id = resp.json()["id"]

    resp = await client.get(f"/api/v1/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["pipeline_name"] == "flow-nome"
    assert resp.json()["pipeline_id"] == pipeline_id

    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 200
    item = next(i for i in resp.json()["items"] if i["id"] == run_id)
    assert item["pipeline_name"] == "flow-nome"


@pytest.mark.asyncio
async def test_run_executa_com_build_pipeline_graph(client: AsyncClient, monkeypatch):
    """Executor usa build_pipeline_graph quando pipeline presente (spy)."""
    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="graph-flow", agent_id="developer"))

    calls = []

    from lf.pipeline.pipeline_graph import build_pipeline_graph as real_build

    def spy(pipeline, agent_templates, checkpointer=None):
        calls.append(True)
        return real_build(pipeline, agent_templates, checkpointer=checkpointer)

    monkeypatch.setattr("lf.pipeline.pipeline_graph.build_pipeline_graph", spy)

    resp = await client.post("/api/v1/runs", json={"idea": "grafo custom", "pipeline_id": pipeline_id})
    assert resp.status_code == 201, resp.text
    final = await _wait_terminal(client, resp.json()["id"])
    assert final["status"] in ("completed", "failed"), final
    assert calls, "build_pipeline_graph não foi chamado pelo executor"


@pytest.mark.asyncio
async def test_run_agente_biblioteca_registrado_no_grafo(client: AsyncClient, monkeypatch):
    """Pipeline com agente da biblioteca roda (nó agent:<slug> via register_agent_node)."""
    agent_resp = await client.post(
        "/api/v1/agents",
        json={
            "name": "helperzinho",
            "description": "helper de teste",
            "prompt": "Voce e um helper",
        },
    )
    assert agent_resp.status_code == 201, agent_resp.text
    agent_id = agent_resp.json()["id"]

    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="bib-flow", agent_id=agent_id))
    resp = await client.post("/api/v1/runs", json={"idea": "com agente biblioteca", "pipeline_id": pipeline_id})
    assert resp.status_code == 201, resp.text

    final = await _wait_terminal(client, resp.json()["id"])
    assert final["status"] in ("completed", "failed"), final
    assert "unknown agent" not in (final.get("logs") or "")


@pytest.mark.asyncio
async def test_run_agente_deletado_erro_claro(client: AsyncClient):
    """Agente da biblioteca deletado → revalidação no start falha com erro claro (422, não crash)."""
    agent_resp = await client.post(
        "/api/v1/agents",
        json={"name": "sumido", "prompt": "Vou sumir"},
    )
    assert agent_resp.status_code == 201, agent_resp.text
    agent_id = agent_resp.json()["id"]

    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="sum-flow", agent_id=agent_id))

    del_resp = await client.delete(f"/api/v1/agents/{agent_id}")
    assert del_resp.status_code == 200, del_resp.text

    resp = await client.post("/api/v1/runs", json={"idea": "agente sumiu", "pipeline_id": pipeline_id})
    assert resp.status_code == 422, resp.text
    assert "agent node references unknown agent" in resp.json()["detail"]


def test_executor_agente_desconhecido_levanta_erro_claro():
    """Mecanismo de execução: build_pipeline_graph com agente fora dos templates → ValueError claro.

    Se o agente sumir entre o snapshot (start da run) e a execução, o
    TaskDispatcher._get_graph levanta ValueError('unknown agent node') — o
    try/except de _run_pipeline converte em run failed com log claro.
    """
    from lf.api.pipelines import PipelineBase
    from lf.orchestrator.task_dispatcher import TaskDispatcher

    pipeline = PipelineBase(
        name="ghost-agent",
        description="",
        nodes=[
            {"id": "n1", "type": "input"},
            {"id": "n2", "type": "agent", "agent_id": "agente-deletado"},
            {"id": "n3", "type": "output"},
        ],
        edges=[
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
        ],
    )
    dispatcher = TaskDispatcher(pipeline=pipeline, agent_templates={})
    with pytest.raises(ValueError, match="unknown agent node: agente-deletado"):
        dispatcher._get_graph()


@pytest.mark.asyncio
async def test_migracao_aditiva_pipeline_snapshot(tmp_path):
    """DB legado (sem pipeline_id/pipeline_snapshot) ganha colunas via ALTER, dado preservado."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from lf.api.database import _apply_pipeline_runs_additive_migration

    db_path = tmp_path / "legacy.sqlite"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.exec_driver_sql(
            "CREATE TABLE pipeline_runs (id VARCHAR(36) PRIMARY KEY, idea TEXT, status VARCHAR(20))"
        )
        await conn.exec_driver_sql(
            "INSERT INTO pipeline_runs (id, idea, status) VALUES ('run-legacy-1', 'old idea', 'done')"
        )

    async with eng.begin() as conn:
        await _apply_pipeline_runs_additive_migration(conn)

    async with eng.begin() as conn:
        res = await conn.exec_driver_sql("PRAGMA table_info(pipeline_runs)")
        cols = {row[1] for row in res.fetchall()}
        assert "pipeline_snapshot" in cols
        assert "pipeline_id" in cols
        row = (await conn.exec_driver_sql("SELECT idea FROM pipeline_runs WHERE id='run-legacy-1'")).fetchone()
        assert row[0] == "old idea"

    # Idempotente: rodar de novo sem erro
    async with eng.begin() as conn:
        await _apply_pipeline_runs_additive_migration(conn)

    await eng.dispose()


def _install_graph_spies(monkeypatch) -> list[str]:
    """Instala spys em build_pipeline_graph/build_graph; retorna lista de chamadas.

    Rótulos: 'pg' (build_pipeline_graph — grafo custom), 'bg-exec'
    (build_graph via TaskDispatcher._get_graph — executor default), 'bg-aux'
    (build_graph via _checkpoint_next_nodes/costs — consulta M-10 de checkpoint,
    ruído esperado que NÃO indica qual grafo a run executou).
    """
    from lf.pipeline.pipeline_graph import build_pipeline_graph as real_build_pg
    from lf.pipeline.graph import build_graph as real_build_graph

    calls: list[str] = []

    def spy_pg(pipeline, agent_templates, checkpointer=None):
        calls.append("pg")
        return real_build_pg(pipeline, agent_templates, checkpointer=checkpointer)

    def spy_bg_exec(*args, **kwargs):
        calls.append("bg-exec")
        return real_build_graph(*args, **kwargs)

    def spy_bg_aux(*args, **kwargs):
        calls.append("bg-aux")
        return real_build_graph(*args, **kwargs)

    monkeypatch.setattr("lf.pipeline.pipeline_graph.build_pipeline_graph", spy_pg)
    # task_dispatcher importa build_graph no topo (binding direto) — spy lá
    # captura EXATAMENTE o executor default (_get_graph); o spy em
    # lf.pipeline.graph.build_graph captura os acessórios (helper M-10).
    monkeypatch.setattr("lf.orchestrator.task_dispatcher.build_graph", spy_bg_exec)
    monkeypatch.setattr("lf.pipeline.graph.build_graph", spy_bg_aux)
    return calls


async def _wait_calls(calls: list[str], predicate, timeout: float = 60.0) -> None:
    """Aguarda o spy registrar chamadas que satisfazem `predicate`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate(calls):
            return
        await asyncio.sleep(0.3)
    raise AssertionError(f"spy não registrou chamadas esperadas: {calls}")


@pytest.mark.asyncio
async def test_resume_pipeline_usa_snapshot(client: AsyncClient, monkeypatch):
    """Resume de run com pipeline usa build_pipeline_graph (snapshot), NUNCA build_graph.

    Fix round 1 (T5): antes, _resume_run_impl montava TaskDispatcher() sem
    pipeline → resume de run de pipeline executava o grafo default errado.
    """
    calls = _install_graph_spies(monkeypatch)

    pipeline_id = await _create_pipeline(client, _pipeline_payload(name="resume-flow", agent_id="developer"))
    resp = await client.post("/api/v1/runs", json={"idea": "pausa", "pipeline_id": pipeline_id})
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

    final = await _wait_terminal(client, run_id)
    assert final["status"] in ("completed", "failed"), final
    assert calls.count("pg") >= 1, "create não usou build_pipeline_graph"
    assert "bg-exec" not in calls, "create com pipeline usou build_graph no executor"

    calls.clear()

    resp = await client.post(f"/api/v1/runs/{run_id}/resume")
    assert resp.status_code == 200, resp.text
    await _wait_calls(calls, lambda c: c.count("pg") >= 1)
    assert "bg-exec" not in calls, "resume usou build_graph default em vez do snapshot"


@pytest.mark.asyncio
async def test_resume_sem_snapshot_usa_build_graph(client: AsyncClient, monkeypatch):
    """Run legada sem snapshot: resume mantém comportamento atual (build_graph)."""
    calls = _install_graph_spies(monkeypatch)

    resp = await client.post("/api/v1/runs", json={"idea": "legada"})
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]

    final = await _wait_terminal(client, run_id)
    assert final["status"] in ("completed", "failed"), final
    assert "bg-exec" in calls, "create default não usou build_graph no executor"
    assert "pg" not in calls

    calls.clear()

    resp = await client.post(f"/api/v1/runs/{run_id}/resume")
    assert resp.status_code == 200, resp.text
    await _wait_calls(calls, lambda c: c.count("bg-exec") >= 1)
    assert "pg" not in calls, "resume legado usou build_pipeline_graph"
