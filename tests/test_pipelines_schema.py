"""Testes de schema de pipelines (S3 — editor de pipelines).

Cobre PipelineNode/PipelineEdge/PipelineBase/PipelineCreate/PipelineUpdate/
PipelineResponse (validação pydantic v2, incluindo edge conditional com
condition obrigatória via model_validator) e o modelo ORM PipelineTemplate.
"""

import contextlib
import os
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from pydantic import ValidationError

from lf.api.pipelines import (
    PipelineCreate,
    PipelineEdge,
    PipelineNode,
    PipelineResponse,
    PipelineUpdate,
)
from lf.api.models import Base, PipelineTemplate


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Configura banco SQLite de teste limpo para cada teste (padrão S2)."""
    from lf.api.database import Base as DBBase, close_db, engine, init_db

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
            await conn.run_sync(DBBase.metadata.drop_all)
            await conn.run_sync(DBBase.metadata.create_all)
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


# ─── PipelineNode: validação ───────────────────────────────────────────────
def test_node_type_invalido_falha():
    with pytest.raises(ValidationError):
        PipelineNode(id="n1", type="foo")


def test_node_id_vazio_falha():
    with pytest.raises(ValidationError):
        PipelineNode(id="", type="agent")


def test_node_defaults():
    node = PipelineNode(id="n1", type="agent")
    assert node.agent_id is None
    assert node.config == {}


def test_node_todos_os_tipos_aceitos():
    for t in ("agent", "split", "merge", "input", "output", "gate"):
        assert PipelineNode(id=f"n-{t}", type=t).type == t


def test_node_agent_id_opcional():
    node = PipelineNode(id="n1", type="agent", agent_id="agent-1", config={"k": "v"})
    assert node.agent_id == "agent-1"
    assert node.config == {"k": "v"}


# ─── PipelineEdge: validação ───────────────────────────────────────────────
def test_edge_defaults():
    edge = PipelineEdge(source="a", target="b")
    assert edge.type == "sequential"
    assert edge.max_retries == 2
    assert edge.condition is None


def test_edge_type_invalido_falha():
    with pytest.raises(ValidationError):
        PipelineEdge(source="a", target="b", type="loop")


def test_edge_conditional_sem_condition_falha():
    with pytest.raises(ValidationError):
        PipelineEdge(source="a", target="b", type="conditional")


def test_edge_conditional_com_condition_ok():
    edge = PipelineEdge(source="a", target="b", type="conditional", condition="result.ok")
    assert edge.condition == "result.ok"


def test_edge_retry_max_retries_default_2():
    edge = PipelineEdge(source="a", target="b", type="retry")
    assert edge.max_retries == 2


def test_edge_max_retries_negativo_falha():
    with pytest.raises(ValidationError):
        PipelineEdge(source="a", target="b", max_retries=-1)


# ─── PipelineBase/Create: validação ────────────────────────────────────────
def test_pipeline_name_vazio_falha():
    with pytest.raises(ValidationError):
        PipelineCreate(name="")


def test_pipeline_defaults():
    pipe = PipelineCreate(name="pipe")
    assert pipe.description == ""
    assert pipe.nodes == []
    assert pipe.edges == []


def test_pipeline_aceita_grafo_simples():
    pipe = PipelineCreate(
        name="pipe",
        nodes=[PipelineNode(id="n1", type="agent", agent_id="a1")],
        edges=[PipelineEdge(source="n1", target="n2", type="conditional", condition="ok")],
    )
    assert len(pipe.nodes) == 1
    assert len(pipe.edges) == 1
    assert pipe.nodes[0].type == "agent"


# ─── PipelineUpdate: PATCH-style (PUT com campos omitidos) ─────────────────
def test_update_todos_campos_none_valido():
    update = PipelineUpdate()
    assert update.model_dump(exclude_unset=True) == {}


def test_update_campos_parciais():
    update = PipelineUpdate(name="novo", description="d")
    assert update.name == "novo"
    assert update.nodes is None
    assert update.edges is None


# ─── PipelineResponse: id + timestamps ─────────────────────────────────────
def test_response_inclui_id_e_timestamps():
    now = datetime.now(UTC)
    resp = PipelineResponse(
        id="pipe-1",
        name="pipe",
        created_at=now,
        updated_at=now,
    )
    assert resp.id == "pipe-1"
    assert resp.created_at == now
    assert resp.updated_at == now
    assert isinstance(resp.created_at, datetime)


def test_response_model_validate_de_dict():
    now = datetime.now(UTC)
    data = {
        "id": "pipe-1",
        "name": "pipe",
        "created_at": now,
        "updated_at": now,
    }
    resp = PipelineResponse.model_validate(data)
    assert resp.description == ""
    assert resp.nodes == []
    assert resp.edges == []


# ─── PipelineTemplate: ORM ─────────────────────────────────────────────────
def test_pipeline_template_registrado_no_metadata():
    assert "pipeline_templates" in Base.metadata.tables
    table = Base.metadata.tables["pipeline_templates"]
    assert PipelineTemplate.__tablename__ == "pipeline_templates"
    for col in ("id", "name", "description", "nodes", "edges", "created_at", "updated_at"):
        assert col in table.columns, f"coluna ausente: {col}"


def test_pipeline_template_name_unique():
    table = Base.metadata.tables["pipeline_templates"]
    assert table.columns["name"].unique is True


@pytest.mark.asyncio
async def test_pipeline_template_roundtrip():
    """Cria/consulta PipelineTemplate no SQLite (fixture padrão S2)."""
    from lf.api.database import engine

    from sqlalchemy.ext.asyncio import AsyncSession

    payload = {
        "name": "pipe",
        "description": "meu pipeline",
        "nodes": [{"id": "n1", "type": "agent", "agent_id": "a1", "config": {}}],
        "edges": [{"source": "n1", "target": "n2", "type": "retry", "max_retries": 3}],
    }
    async with AsyncSession(engine) as session:
        row = PipelineTemplate(**payload)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        assert isinstance(row.id, str) and len(row.id) == 36
        assert row.nodes == payload["nodes"]
        assert row.edges == payload["edges"]
        assert row.edges[0]["type"] == "retry"
        assert row.created_at is not None
        assert row.updated_at is not None
