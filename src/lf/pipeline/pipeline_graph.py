"""build_pipeline_graph (S3 — editor de pipelines, T4).

Compila um StateGraph LangGraph a partir do PipelineSchema pydantic
(lf.api.pipelines.PipelineBase) + templates de agentes (dict id → AgentBase).

Semântica v1 (limites documentados, não inventados):
- node 'agent': agent_id ∈ SPECIAL_AGENT_IDS → função real do grafo nativo
  (NodeRegistry, mesmo do build_graph default); senão agente da biblioteca →
  register_agent_node(template) (node_factory S2) e usa o nó compilado.
- 'split'/'merge': nós pass-through vazios — fan-out/fan-in via edges.
- 'gate': router condicional — edges 'conditional' avaliam ``state.get(condition)``
  truthy → target; nenhuma condição satisfeita → END (sem else-branch na v1).
- 'input': ponto de entrada único (exatamente 1); 'output': terminal → END.
- edge 'retry': self-loop com teto via ``attempt_count`` do GraphState (canal
  já declarado — evita adicionar canal novo). O nó fonte é envolvido num
  wrapper que incrementa ``attempt_count`` por execução; router decide retry
  enquanto ``attempt_count < max_retries``, senão segue para o edge normal
  seguinte (ou END). Regras: retry edge DEVE ser self-loop (target == source)
  e o nó fonte não pode ter >1 edge de saída não-retry (router único).
- Nome do nó no grafo = node.id do schema (único no pipeline); o registro no
  NodeRegistry global (chave ``agent:<slug>``) é efeito colateral do
  register_agent_node, usado por reuso/inspeção.

Limitações v1 (documentadas): retry só self-loop com teto; gates sem
else-branch (falsy → END); SEM nós custom runtime; edges 'conditional' só
partem de gates (não-gate com conditional → ValueError defensivo).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph

from lf.api.agents import AgentBase
from lf.api.pipeline_validator import SPECIAL_AGENT_IDS
from lf.api.pipelines import PipelineBase
from lf.pipeline.graph import NodeRegistry
from lf.pipeline.node_factory import register_agent_node
from lf.pipeline.state import GraphState


def _noop(state: GraphState) -> dict:
    """Pass-through vazio — split/merge/gate/input/output são estrutura via edges."""
    return {}


def _attempt_counter(node: Callable) -> Callable:
    """Envolve um nó com retry self-loop: incrementa ``attempt_count`` por execução.

    O contador é a fonte de verdade do router de retry (teto = max_retries da
    edge). Usa o canal ``attempt_count`` já declarado no GraphState — não
    muta estado fora do retorno do nó (nota do graph.py: should_retry não
    muta; mutação de edge não propaga).
    """

    def wrapped(state: GraphState, config: Optional[RunnableConfig] = None) -> dict:
        out = node(state, config)
        return {**out, "attempt_count": int(state.get("attempt_count", 0)) + 1}

    return wrapped


def _retry_router(max_retries: int, retry_target: str, next_target: str) -> Callable:
    """Router de retry: enquanto ``attempt_count < max_retries`` e sem doom-loop volta ao fonte."""

    def router(state: GraphState) -> str:
        if state.get("doom_loop_detected"):
            return next_target
        attempts = int(state.get("attempt_count", 0))
        return retry_target if attempts < max_retries else next_target

    return router


def _gate_router(conditions: list[tuple[str, str]]) -> Callable:
    """Router de gate: primeira condição truthy no state vence; senão END."""

    def router(state: GraphState) -> str:
        for condition, target in conditions:
            if state.get(condition):
                return target
        return END

    return router


def build_pipeline_graph(
    pipeline: PipelineBase,
    agent_templates: dict[str, AgentBase],
    checkpointer: Any | None = None,
):
    """Compila o StateGraph do pipeline.

    ``agent_templates``: dict id → AgentBase (os agentes da biblioteca).
    Agentes ausentes (nem especiais nem templates) → ValueError (assert
    defensivo — validate_pipeline pega antes, no endpoint).
    """
    if pipeline is None:
        raise ValueError("pipeline is required")
    if not pipeline.nodes:
        raise ValueError("pipeline has no nodes")
    if not pipeline.edges:
        raise ValueError("pipeline has no edges")

    node_ids = {n.id for n in pipeline.nodes}
    inputs = [n for n in pipeline.nodes if n.type == "input"]
    outputs = [n for n in pipeline.nodes if n.type == "output"]
    if len(inputs) != 1:
        raise ValueError("pipeline requires exactly one input node")
    if len(outputs) != 1:
        raise ValueError("pipeline requires exactly one output node")

    # refs válidas (assert defensivo — o endpoint valida antes)
    for e in pipeline.edges:
        if e.source not in node_ids or e.target not in node_ids:
            raise ValueError(f"edge references unknown node: {e.source or e.target}")

    # edges por nó fonte
    out_by_source: dict[str, list] = {}
    for e in pipeline.edges:
        out_by_source.setdefault(e.source, []).append(e)

    retry_sources: dict[str, tuple[int, str]] = {}  # source_id -> (max_retries, next_target_id)
    for sid, edges in out_by_source.items():
        retry_edges = [e for e in edges if e.type == "retry"]
        if not retry_edges:
            continue
        if len(retry_edges) > 1:
            raise ValueError(f"multiple retry edges from node: {sid}")
        re_ = retry_edges[0]
        if re_.target != sid:
            raise ValueError(f"retry edge must be a self-loop in v1: {sid} -> {re_.target}")
        normal = [e for e in edges if e.type != "retry"]
        if len(normal) > 1:
            raise ValueError(f"retry node requires at most one normal outgoing edge: {sid}")
        next_target = normal[0].target if normal else None
        retry_sources[sid] = (re_.max_retries, next_target)

    workflow = StateGraph(GraphState)

    # resolve nós (retry wrapper aplicado antes do add_node)
    for node in pipeline.nodes:
        if node.type == "agent":
            if node.agent_id in SPECIAL_AGENT_IDS:
                fn = NodeRegistry.get_all()[node.agent_id]
            elif node.agent_id in agent_templates:
                registered_key = register_agent_node(agent_templates[node.agent_id])
                fn = NodeRegistry.get_all()[registered_key]
            else:
                raise ValueError(f"unknown agent node: {node.agent_id}")
        elif node.type in ("split", "merge", "gate", "input", "output"):
            fn = _noop
        else:
            raise ValueError(f"unsupported node type: {node.type}")

        if node.id in retry_sources:
            fn = _attempt_counter(fn)
        workflow.add_node(node.id, fn)

    # ponto de entrada e saída
    workflow.set_entry_point(inputs[0].id)
    workflow.add_edge(outputs[0].id, END)

    # edges
    for sid, edges in out_by_source.items():
        source_node = next(n for n in pipeline.nodes if n.id == sid)
        if source_node.type == "gate":
            if any(e.type != "conditional" or not (e.condition or "").strip() for e in edges):
                raise ValueError(f"gate node requires conditional edges: {sid}")
            mapping = {e.target: e.target for e in edges}
            mapping["__end__"] = END
            workflow.add_conditional_edges(sid, _gate_router([(e.condition, e.target) for e in edges]), mapping)
            continue

        if sid in retry_sources:
            max_retries, next_target = retry_sources[sid]
            next_key = next_target if next_target else END
            # router retorna sid (retry) ou next_key (estourou) — mapping chave→nó
            mapping = {sid: sid, next_key: next_key}
            workflow.add_conditional_edges(sid, _retry_router(max_retries, sid, next_key), mapping)
            continue

        for e in edges:
            if e.type == "conditional":
                raise ValueError(f"conditional edges only supported from gate nodes: {sid} -> {e.target}")
            workflow.add_edge(sid, e.target)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=None)
