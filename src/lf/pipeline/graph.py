"""
Grafo LangGraph: StateGraph, router condicional, build_graph.
Centraliza toda a lógica de roteamento e suporte a auditoria simultânea (AppSec + DevOps paralelos).
"""
from __future__ import annotations

from typing import Any, Literal
from langgraph.graph import END, StateGraph

from .nodes.appsec import appsec
from .nodes.cpo import cpo
from .nodes.developer import developer
from .nodes.devops import devops
from .nodes.parallel_audit import parallel_audit
from .nodes.pm import product_manager
from .nodes.qa import qa
from .nodes.tech_lead import tech_lead
from .nodes.test_writer import test_writer
from .state import GraphState


def entry_router(state: GraphState) -> Literal["cpo", "tech_lead", "developer", "qa"]:
    """Decide o nó de entrada inicial (patch, review-only, explore, full)."""
    routing_mode = state.get("routing_mode", "full")
    task_type = state.get("task_type", "feature")

    if routing_mode in ("patch", "fast") or task_type in ("patch", "bugfix", "fast", "simple"):
        print("--- ROTEAMENTO ADAPTATIVO: Modo PATCH/FAST (Developer -> QA) ---")
        return "developer"

    if routing_mode == "review-only" or task_type == "review":
        print("--- ROTEAMENTO ADAPTATIVO: Modo REVIEW-ONLY (QA -> Parallel Audit) ---")
        return "qa"

    if routing_mode == "explore" or task_type == "explore":
        print("--- ROTEAMENTO ADAPTATIVO: Modo EXPLORE (Tech Lead Spike) ---")
        return "tech_lead"

    print("--- ROTEAMENTO ADAPTATIVO: Modo FULL (CPO -> PM -> Tech Lead -> Dev -> QA -> Audit) ---")
    return "cpo"


def router(state: GraphState) -> str:
    """Router único: decide próximo nó baseado no estado.

    Só aceita destinos que existem nos mappings do EdgeRegistry (harmonizado):
    pm, tech_lead, test_writer, developer, qa. Qualquer outro next_agent cai em END em vez de
    disparar ValueError do LangGraph por chave ausente no mapping do nó fonte.
    """
    next_agent = state.get("next_agent", "cpo")

    if next_agent in ("FINISH", "__end__", None):
        return END

    if next_agent in ("pm", "tech_lead", "test_writer", "developer", "qa"):
        return next_agent

    return END


def should_retry(state: GraphState) -> Literal["parallel_audit", "developer", "__end__"]:
    """Decide após QA se deve prosseguir para a auditoria simultânea (AppSec + DevOps) ou retentar."""
    test_report = state.get("test_report", {})
    tests_failed = test_report.get("summary", {}).get("tests_failed", 1) if isinstance(test_report, dict) else 1
    qa_attempt = state.get("qa_attempt_count", 0)
    max_retries = state.get("max_retries", 3)

    if tests_failed == 0:
        return "parallel_audit"

    if qa_attempt < max_retries:
        return "developer"

    # NOTA: NÃO mutar o estado aqui — should_retry é função de aresta condicional do LangGraph
    # e mutações in-place não propagam para o estado final. O erro de retries esgotados é
    # setado dentro do nó parallel_audit (cujo retorno é propagado pelo grafo).
    print("--- AVISO: Retentativas de QA esgotadas. Executando auditoria final e gerando lições aprendidas... ---")
    return "parallel_audit"


class NodeRegistry:
    """Registro desacoplado de nós do pipeline LangGraph."""
    _nodes: dict[str, any] = {
        "cpo": cpo,
        "pm": product_manager,
        "tech_lead": tech_lead,
        "test_writer": test_writer,
        "developer": developer,
        "qa": qa,
        "appsec": appsec,
        "devops": devops,
        "parallel_audit": parallel_audit,
    }

    @classmethod
    def register(cls, name: str, node_func: any) -> None:
        cls._nodes[name] = node_func

    @classmethod
    def get_all(cls) -> dict[str, any]:
        return dict(cls._nodes)


class EdgeRegistry:
    """Registro desacoplado de transições entre nós do grafo."""
    _conditional_edges: dict[str, dict[str, str]] = {
        "cpo": {"pm": "pm", "__end__": END},
        "pm": {"tech_lead": "tech_lead", "__end__": END},
        "tech_lead": {"test_writer": "test_writer", "__end__": END},
        "test_writer": {"developer": "developer", "__end__": END},
        "developer": {"qa": "qa", "__end__": END},
        "parallel_audit": {"developer": "developer", "__end__": END},
    }

    @classmethod
    def register(cls, source_node: str, targets: dict[str, str]) -> None:
        if source_node not in cls._conditional_edges:
            cls._conditional_edges[source_node] = {}
        cls._conditional_edges[source_node].update(targets)

    @classmethod
    def get_edges(cls, source_node: str) -> dict[str, str]:
        return dict(cls._conditional_edges.get(source_node, {}))


def build_graph(
    checkpointer: Any | None = None,  # InMemorySaver | SqliteSaver | AsyncSqliteSaver
    interrupt_after: list[str] | None = None,
    human_gate_enabled: bool = False,
):
    """Constrói e compila o grafo com checkpointing, auditoria paralela e human-in-the-loop opcional."""
    workflow = StateGraph(GraphState)

    for node_name, node_func in NodeRegistry.get_all().items():
        workflow.add_node(node_name, node_func)

    workflow.set_conditional_entry_point(
        entry_router,
        {
            "cpo": "cpo",
            "tech_lead": "tech_lead",
            "developer": "developer",
            "qa": "qa",
        },
    )

    for source_node in NodeRegistry.get_all():
        if source_node == "qa":
            workflow.add_conditional_edges(
                "qa",
                should_retry,
                {
                    "parallel_audit": "parallel_audit",
                    "developer": "developer",
                    "__end__": END,
                },
            )
        else:
            edges = EdgeRegistry.get_edges(source_node)
            if edges:
                workflow.add_conditional_edges(source_node, router, edges)

    gates = list(interrupt_after) if interrupt_after else []
    if human_gate_enabled:
        for n in ("developer", "qa", "parallel_audit"):
            if n not in gates:
                gates.append(n)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=gates or None)
