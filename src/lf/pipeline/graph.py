"""
Grafo LangGraph: StateGraph, router condicional, build_graph.
Centraliza toda a lógica de roteamento e suporte a auditoria simultânea (AppSec + DevOps paralelos).
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from .nodes.appsec import appsec
from .nodes.cpo import cpo
from .nodes.developer import developer
from .nodes.devops import devops
from .nodes.parallel_audit import parallel_audit
from .nodes.pm import product_manager
from .nodes.qa import qa
from .nodes.tech_lead import tech_lead
from .state import GraphState


def entry_router(state: GraphState) -> Literal["cpo", "developer"]:
    """Decide o nó de entrada inicial (Fast-Path vs Full-Path)."""
    routing_mode = state.get("routing_mode", "full")
    task_type = state.get("task_type", "feature")

    if routing_mode == "fast" or task_type in ("fast", "bugfix", "refactor", "simple"):
        print("--- ROTEAMENTO ADAPTATIVO: Ativando FAST-PATH (Developer -> QA -> Parallel Audit) ---")
        return "developer"

    print("--- ROTEAMENTO ADAPTATIVO: Ativando FULL-PATH (CPO -> PM -> Tech Lead -> Dev -> QA -> Parallel Audit) ---")
    return "cpo"


def router(state: GraphState) -> str:
    """Router único: decide próximo nó baseado no estado."""
    next_agent = state.get("next_agent", "cpo")

    if next_agent in ("FINISH", "__end__", None):
        return END

    if next_agent in ("cpo", "pm", "tech_lead", "developer", "qa", "appsec", "devops", "parallel_audit"):
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

    return END


def build_graph(
    checkpointer: InMemorySaver | None = None,
    interrupt_after: list[str] | None = None,
    human_gate_enabled: bool = False,
):
    """Constrói e compila o grafo com checkpointing, auditoria paralela e human-in-the-loop opcional."""
    workflow = StateGraph(GraphState)

    workflow.add_node("cpo", cpo)
    workflow.add_node("pm", product_manager)
    workflow.add_node("tech_lead", tech_lead)
    workflow.add_node("developer", developer)
    workflow.add_node("qa", qa)
    workflow.add_node("appsec", appsec)
    workflow.add_node("devops", devops)
    workflow.add_node("parallel_audit", parallel_audit)

    workflow.set_conditional_entry_point(
        entry_router,
        {
            "cpo": "cpo",
            "developer": "developer",
        },
    )

    workflow.add_conditional_edges("cpo", router, {"pm": "pm", "__end__": END})
    workflow.add_conditional_edges("pm", router, {"tech_lead": "tech_lead", "__end__": END})
    workflow.add_conditional_edges("tech_lead", router, {"developer": "developer", "__end__": END})
    workflow.add_conditional_edges("developer", router, {"qa": "qa", "__end__": END})

    # QA decide: passou → parallel_audit (AppSec + DevOps simultâneos), falhou → retry developer
    workflow.add_conditional_edges(
        "qa",
        should_retry,
        {
            "parallel_audit": "parallel_audit",
            "developer": "developer",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "parallel_audit",
        router,
        {
            "developer": "developer",
            "__end__": END,
        },
    )

    gates = list(interrupt_after) if interrupt_after else []
    if human_gate_enabled:
        for n in ("developer", "qa", "parallel_audit"):
            if n not in gates:
                gates.append(n)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=gates or None)
