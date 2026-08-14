"""Testes do build_pipeline_graph (S3 — T4): compila StateGraph do PipelineSchema.

Compilar NÃO executa LLM; os testes que invocam o grafo usam agente da
biblioteca com call_llm_via_opencode mockado (padrão test_node_factory.py).
"""

import pytest

from lf.api.agents import AgentBase
from lf.api.pipelines import PipelineBase, PipelineEdge, PipelineNode
from lf.pipeline.graph import NodeRegistry
from lf.pipeline.pipeline_graph import build_pipeline_graph
from lf.pipeline.state import GraphState


def _template(name: str = "helper", **over) -> AgentBase:
    d = dict(
        name=name,
        description="",
        prompt="do the thing",
        model="default",
        temperature=0.7,
        max_retries=2,
        timeout_seconds=300,
        env_vars={},
        tools_allowlist=[],
        permissions=[],
        stack="python",
        budget_usd=0.0,
    )
    d.update(over)
    return AgentBase(**d)


def _pipeline(nodes: list[PipelineNode], edges: list[PipelineEdge], name: str = "flow") -> PipelineBase:
    return PipelineBase(name=name, description="", nodes=nodes, edges=edges)


def _state(**over) -> dict:
    """State GraphState completo — canais obrigatórios preenchidos para invoke."""
    s: dict = dict(
        idea="x",
        output_dir="/tmp/x",
        epic={},
        user_stories=[],
        tech_spec="",
        contract_tests="",
        code="",
        test_report={},
        security_review={},
        devops_manifest={},
        ontology_path="",
        project_dir="",
        stack="python",
        next_agent="",
        attempt_count=0,
        qa_attempt_count=0,
        appsec_attempt_count=0,
        max_retries=3,
        error=None,
        feedback_history=[],
        mock_llm=True,
        llm_provider="oc",
        llm_model_name="x",
        llm_temperature=0.0,
        is_interactive=False,
        read_only=False,
        routing_mode="full",
        task_type="feature",
        complexity_level="mvp",
        expected_schema=None,
        persona_id=None,
        circuit_breaker={},
    )
    s.update(over)
    return s


def _node_edges(g) -> set[tuple[str, str, bool]]:
    return {(e.source, e.target, e.conditional) for e in g.get_graph().edges}


# ---------------------------------------------------------------- linear


def test_linear_pipeline_compiles_structure():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="dev", type="agent", agent_id="developer"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="dev"),
            PipelineEdge(source="dev", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {})
    gg = g.get_graph()
    names = set(gg.nodes.keys())
    assert {"__start__", "in", "dev", "out", "__end__"} <= names
    edges = _node_edges(g)
    assert ("in", "dev", False) in edges
    assert ("dev", "out", False) in edges
    assert ("out", "__end__", False) in edges


# ---------------------------------------------------------------- split/merge


def test_split_fan_out():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="sp", type="split"),
            PipelineNode(id="a", type="agent", agent_id="developer"),
            PipelineNode(id="b", type="agent", agent_id="developer"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="sp"),
            PipelineEdge(source="sp", target="a"),
            PipelineEdge(source="sp", target="b"),
            PipelineEdge(source="a", target="out"),
            PipelineEdge(source="b", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {})
    edges = _node_edges(g)
    assert ("sp", "a", False) in edges
    assert ("sp", "b", False) in edges


def test_merge_fan_in():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="a", type="agent", agent_id="developer"),
            PipelineNode(id="b", type="agent", agent_id="developer"),
            PipelineNode(id="mg", type="merge"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="a"),
            PipelineEdge(source="in", target="b"),
            PipelineEdge(source="a", target="mg"),
            PipelineEdge(source="b", target="mg"),
            PipelineEdge(source="mg", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {})
    edges = _node_edges(g)
    assert ("a", "mg", False) in edges
    assert ("b", "mg", False) in edges


# ---------------------------------------------------------------- gate


def test_gate_conditional_routes_on_state(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "lf.pipeline.node_factory.call_llm_via_opencode",
        lambda **kw: calls.append(kw) or "mock ok",
    )
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="gate", type="gate"),
            PipelineNode(id="lib", type="agent", agent_id="lib-1"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="gate"),
            PipelineEdge(source="gate", target="lib", type="conditional", condition="task_type"),
            PipelineEdge(source="lib", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {"lib-1": _template()})
    edges = _node_edges(g)
    assert ("gate", "lib", True) in edges

    res = g.invoke(_state(task_type="feature"))  # truthy → lib roda
    assert res["next_agent"] == "FINISH"  # nó lib rodou
    assert len(calls) == 1

    res2 = g.invoke(_state(task_type=""))  # falsy → END, lib não roda
    assert res2["next_agent"] == ""
    assert len(calls) == 1


# ---------------------------------------------------------------- retry


def test_retry_self_loop_enforces_cap(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "lf.pipeline.node_factory.call_llm_via_opencode",
        lambda **kw: calls.append(kw) or "mock ok",
    )
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="lib", type="agent", agent_id="lib-1"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="lib"),
            PipelineEdge(source="lib", target="lib", type="retry", max_retries=2),
            PipelineEdge(source="lib", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {"lib-1": _template()})
    res = g.invoke(_state())
    assert res["attempt_count"] == 2  # teto max_retries=2 → 2 execuções
    assert len(calls) == 2


def test_retry_non_self_loop_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="a", type="agent", agent_id="developer"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="a"),
            PipelineEdge(source="a", target="out", type="retry", max_retries=2),
        ],
    )
    with pytest.raises(ValueError, match="self-loop"):
        build_pipeline_graph(p, {})


def test_retry_conflicting_edges_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="a", type="agent", agent_id="developer"),
            PipelineNode(id="b", type="agent", agent_id="developer"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="a"),
            PipelineEdge(source="a", target="a", type="retry", max_retries=2),
            PipelineEdge(source="a", target="b"),
            PipelineEdge(source="a", target="out"),
        ],
    )
    with pytest.raises(ValueError, match="retry"):
        build_pipeline_graph(p, {})


# ---------------------------------------------------------------- agentes


def test_library_agent_registered_in_noderegistry():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="lib", type="agent", agent_id="lib-1"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="lib"),
            PipelineEdge(source="lib", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {"lib-1": _template(name="helper")})
    assert "agent:helper" in NodeRegistry.get_all()
    names = set(g.get_graph().nodes.keys())
    assert "lib" in names


def test_special_agent_does_not_register(monkeypatch):
    calls = []
    real = __import__("lf.pipeline.pipeline_graph", fromlist=["register_agent_node"]).register_agent_node
    monkeypatch.setattr("lf.pipeline.pipeline_graph.register_agent_node", lambda a: calls.append(a) or real(a))
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="dev", type="agent", agent_id="developer"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="dev"),
            PipelineEdge(source="dev", target="out"),
        ],
    )
    g = build_pipeline_graph(p, {})
    assert calls == []
    assert "dev" in g.get_graph().nodes.keys()


def test_unknown_agent_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="ghost", type="agent", agent_id="ghost"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="ghost"),
            PipelineEdge(source="ghost", target="out"),
        ],
    )
    with pytest.raises(ValueError, match="unknown agent"):
        build_pipeline_graph(p, {})


# ---------------------------------------------------------------- estrutural


def test_edge_unknown_node_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in", type="input"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in", target="ghost"),
        ],
    )
    with pytest.raises(ValueError, match="unknown node"):
        build_pipeline_graph(p, {})


def test_two_inputs_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="in1", type="input"),
            PipelineNode(id="in2", type="input"),
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="in1", target="out"),
            PipelineEdge(source="in2", target="out"),
        ],
    )
    with pytest.raises(ValueError, match="exactly one input"):
        build_pipeline_graph(p, {})


def test_missing_input_raises():
    p = _pipeline(
        nodes=[
            PipelineNode(id="out", type="output"),
        ],
        edges=[
            PipelineEdge(source="out", target="out", type="retry", max_retries=2),
        ],
    )
    with pytest.raises(ValueError, match="exactly one input"):
        build_pipeline_graph(p, {})


def test_empty_pipeline_raises():
    with pytest.raises(ValueError, match="nodes"):
        build_pipeline_graph(_pipeline(nodes=[], edges=[]), {})
