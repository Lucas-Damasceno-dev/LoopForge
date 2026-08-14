"""Testes do validador semântico de pipelines + endpoint validate (S3 T3).

Validador puro (sem DB — known_agents passado como parâmetro) + endpoint
POST /api/v1/pipelines/{pipeline_id}/validate (usa agent_templates do DB).
Padrão de fixture do test_agents_api.py para os testes de endpoint.
"""

import contextlib
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from lf.api.pipeline_validator import SPECIAL_AGENT_IDS, validate_pipeline
from lf.api.pipelines import PipelineBase, PipelineEdge, PipelineNode
from lf.api.app import create_app


def node(id_: str, type_: str = "agent", **kw) -> PipelineNode:
    data = {"id": id_, "type": type_}
    data.update(kw)
    return PipelineNode(**data)


def edge(source: str, target: str, **kw) -> PipelineEdge:
    return PipelineEdge(source=source, target=target, **kw)


def build(nodes: list[PipelineNode], edges: list[PipelineEdge], **kw) -> PipelineBase:
    return PipelineBase(name="flow", nodes=nodes, edges=edges, **kw)


# ─── Validador puro ───────────────────────────────────────────────────────


def test_pipeline_minimal_valida():
    """input → agent → output é válido (errors == [])."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "out")],
    )
    assert validate_pipeline(p, known_agents=set()) == []


def test_pipeline_vazio_sem_nodes_e_sem_edges():
    """PipelineBase() vazio → erros de nodes e edges."""
    errors = validate_pipeline(PipelineBase(name="vazio"), known_agents=set())
    assert "pipeline has no nodes" in errors
    assert "pipeline has no edges" in errors


def test_edge_source_desconhecido():
    p = build(
        [node("in", "input"), node("out", "output")],
        [edge("ghost", "out")],
    )
    assert "edge references unknown source node: ghost" in validate_pipeline(p, known_agents=set())


def test_edge_target_desconhecido():
    p = build(
        [node("in", "input"), node("out", "output")],
        [edge("in", "ghost")],
    )
    assert "edge references unknown target node: ghost" in validate_pipeline(p, known_agents=set())


def test_conditional_sem_condition_trim():
    """Condition só com espaços falha o trim (pydantic aceita, validador não)."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a", type="conditional", condition="   "), edge("a", "out")],
    )
    assert "conditional edge requires non-empty condition: in -> a" in validate_pipeline(p, known_agents=set())


def test_retry_max_retries_zero():
    """Retry sem teto (max_retries < 1) → erro doom-loop guard."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "a", type="retry", max_retries=0), edge("a", "out")],
    )
    assert "retry edge requires max_retries >= 1: a -> a" in validate_pipeline(p, known_agents=set())


def test_agent_desconhecido():
    """agent_id fora de known_agents e de SPECIAL_AGENT_IDS → erro."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="ghost"), node("out", "output")],
        [edge("in", "a"), edge("a", "out")],
    )
    assert "agent node references unknown agent: a" in validate_pipeline(p, known_agents=set())


def test_agent_especial_aceito_sem_db():
    """developer ∈ SPECIAL_AGENT_IDS → válido mesmo com known_agents vazio."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "out")],
    )
    assert validate_pipeline(p, known_agents=set()) == []
    assert "developer" in SPECIAL_AGENT_IDS


def test_agent_conhecido_db_aceito():
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="agente-1"), node("out", "output")],
        [edge("in", "a"), edge("a", "out")],
    )
    assert validate_pipeline(p, known_agents={"agente-1"}) == []


def test_agent_node_sem_agent_id():
    p = build(
        [node("in", "input"), node("a", "agent"), node("out", "output")],
        [edge("in", "a"), edge("a", "out")],
    )
    assert "agent node requires agent_id: a" in validate_pipeline(p, known_agents=set())


def test_sem_input_node():
    p = build(
        [node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("a", "out")],
    )
    assert "pipeline must have exactly one input node" in validate_pipeline(p, known_agents=set())


def test_dois_input_nodes():
    """2 inputs → erro (build exige exatamente 1 input)."""
    p = build(
        [node("in1", "input"), node("in2", "input"), node("out", "output")],
        [edge("in1", "out"), edge("in2", "out")],
    )
    errors = validate_pipeline(p, known_agents=set())
    assert "pipeline must have exactly one input node" in errors


def test_sem_output_node():
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer")],
        [edge("in", "a")],
    )
    errors = validate_pipeline(p, known_agents=set())
    assert "pipeline must have exactly one output node" in errors
    assert "node has no outgoing edges and is not output: a" in errors


def test_dois_output_nodes():
    """2 outputs → erro (build exige exatamente 1 output)."""
    p = build(
        [node("in", "input"), node("out1", "output"), node("out2", "output")],
        [edge("in", "out1"), edge("in", "out2")],
    )
    errors = validate_pipeline(p, known_agents=set())
    assert "pipeline must have exactly one output node" in errors


def test_ciclo_nao_retry():
    """Ciclo sem nenhuma edge retry → erro."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "in"), edge("a", "out")],
    )
    assert "cycle detected (non-retry)" in validate_pipeline(p, known_agents=set())


def test_ciclo_com_retry_ok():
    """Self-loop retry em 'a' → ciclo permitido (não é erro)."""
    p = build(
        [node("in", "input"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "a", type="retry"), edge("a", "out")],
    )
    assert validate_pipeline(p, known_agents=set()) == []


def test_node_orfao_inalcancavel():
    """Nó sem path do input → erro de órfão (com saída própria p/ não virar dead-end)."""
    p = build(
        [
            node("in", "input"),
            node("a", "agent", agent_id="developer"),
            node("out", "output"),
            node("b", "agent", agent_id="developer"),
        ],
        [edge("in", "a"), edge("a", "out"), edge("b", "a")],
    )
    assert "orphan node not reachable from input: b" in validate_pipeline(p, known_agents=set())


def test_split_menos_de_2_saidas():
    p = build(
        [node("in", "input"), node("s", "split"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "s"), edge("s", "a"), edge("a", "out")],
    )
    assert "split requires >=2 outgoing edges: s" in validate_pipeline(p, known_agents=set())


def test_merge_menos_de_2_entradas():
    p = build(
        [node("in", "input"), node("m", "merge"), node("out", "output")],
        [edge("in", "m"), edge("m", "out")],
    )
    assert "merge requires >=2 incoming edges: m" in validate_pipeline(p, known_agents=set())


def test_dead_end_node_sem_saida():
    """Gate sem outgoing e alcançável → dead-end (decisão: gate também exige saída)."""
    p = build(
        [node("in", "input"), node("g", "gate"), node("a", "agent", agent_id="developer"), node("out", "output")],
        [edge("in", "a"), edge("a", "out"), edge("in", "g")],
    )
    assert "node has no outgoing edges and is not output: g" in validate_pipeline(p, known_agents=set())


# ─── Endpoint /api/v1/pipelines/{id}/validate ─────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Banco SQLite de teste limpo por teste (padrão test_agents_api.py)."""
    from lf.api.database import Base, close_db, engine, init_db

    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    for f in (
        ".loopforge/test_api.sqlite",
        ".loopforge/test_api.sqlite-wal",
        ".loopforge/test_api.sqlite-shm",
    ):
        with contextlib.suppress(Exception):
            os.remove(f)
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
async def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


def _pipeline(nodes=None, edges=None, **kw) -> dict:
    payload = {
        "name": kw.pop("name", "flow"),
        "nodes": nodes
        or [
            {"id": "n1", "type": "input"},
            {"id": "n2", "type": "agent", "agent_id": "developer"},
            {"id": "n3", "type": "output"},
        ],
        "edges": edges or [{"source": "n1", "target": "n2"}, {"source": "n2", "target": "n3"}],
    }
    payload.update(kw)
    return payload


@pytest.mark.asyncio
async def test_validate_endpoint_ok(client: AsyncClient):
    """Pipeline válido (agente especial developer, sem registro em agent_templates)."""
    r = await client.post("/api/v1/pipelines", json=_pipeline())
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.post(f"/api/v1/pipelines/{pid}/validate")
    assert r.status_code == 200
    assert r.json() == {"valid": True, "errors": []}


@pytest.mark.asyncio
async def test_validate_endpoint_usa_agentes_do_db(client: AsyncClient):
    """agent_id de agente cadastrado em agent_templates → válido."""
    r = await client.post("/api/v1/agents", json={"name": "meu-agent", "prompt": "roda"})
    assert r.status_code == 201
    aid = r.json()["id"]

    r = await client.post(
        "/api/v1/pipelines",
        json=_pipeline(
            nodes=[
                {"id": "n1", "type": "input"},
                {"id": "n2", "type": "agent", "agent_id": aid},
                {"id": "n3", "type": "output"},
            ],
        ),
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.post(f"/api/v1/pipelines/{pid}/validate")
    assert r.status_code == 200
    assert r.json() == {"valid": True, "errors": []}


@pytest.mark.asyncio
async def test_validate_endpoint_reporta_erros(client: AsyncClient):
    """Edge com target inexistente → valid false + errors não-vazio."""
    r = await client.post(
        "/api/v1/pipelines",
        json=_pipeline(edges=[{"source": "n1", "target": "nope"}]),
    )
    assert r.status_code == 201
    pid = r.json()["id"]

    r = await client.post(f"/api/v1/pipelines/{pid}/validate")
    assert r.status_code == 200
    body = r.json()
    assert body["valid"] is False
    assert body["errors"]
    assert any("unknown target node" in e for e in body["errors"])


@pytest.mark.asyncio
async def test_validate_endpoint_404(client: AsyncClient):
    r = await client.post("/api/v1/pipelines/nao-existe/validate")
    assert r.status_code == 404
    assert r.json()["detail"] == "Pipeline not found"
