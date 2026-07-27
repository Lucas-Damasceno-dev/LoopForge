#-*- coding: utf-8 -*-
"""
Grafo LangGraph: StateGraph, router condicional, build_graph.
Centraliza toda a lógica de roteamento (evita acoplamento com dispatcher/iteration).
"""
from __future__ import annotations
from typing import Literal
import json

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from .state import GraphState
from .nodes.cpo import cpo
from .nodes.pm import product_manager
from .nodes.tech_lead import tech_lead
from .nodes.developer import developer
from .nodes.qa import qa


# --- Router Centralizado ---
# Toda decisão de roteamento está AQUI, não no dispatcher nem no iteration_manager.
def router(state: GraphState) -> Literal["cpo", "product_manager", "tech_lead",
                                          "developer", "qa", "__end__"]:
    """Router único: decide próximo nó baseado no estado."""
    next_agent = state.get("next_agent", "cpo")
    attempt = state.get("attempt_count", 0)
    max_retries = state.get("max_retries", 3)

    if next_agent == "FINISH":
        return END

    if next_agent in ("cpo", "product_manager", "tech_lead", "developer", "qa"):
        return next_agent

    # Fallback seguro
    return "cpo"


def should_retry(state: GraphState) -> Literal["qa", "developer", "__end__"]:
    """Decide após QA se deve retentar ou finalizar."""
    test_report = state.get("test_report", {})
    tests_failed = test_report.get("summary", {}).get("tests_failed", 1)
    attempt = state.get("attempt_count", 0)
    max_retries = state.get("max_retries", 3)

    if tests_failed == 0:
        return END

    if attempt < max_retries:
        return "developer"

    return END


def build_graph(checkpointer: SqliteSaver | None = None):
    """Constrói e compila o grafo com checkpointing."""
    workflow = StateGraph(GraphState)

    # Adiciona nós
    workflow.add_node("cpo", cpo)
    workflow.add_node("product_manager", product_manager)
    workflow.add_node("tech_lead", tech_lead)
    workflow.add_node("developer", developer)
    workflow.add_node("qa", qa)

    # Entry point
    workflow.set_entry_point("cpo")

    # Arestas condicionais — TODO roteamento centralizado
    workflow.add_conditional_edges("cpo", router, {
        "product_manager": "product_manager",
        "__end__": END,
    })

    workflow.add_conditional_edges("product_manager", router, {
        "tech_lead": "tech_lead",
        "__end__": END,
    })

    workflow.add_conditional_edges("tech_lead", router, {
        "developer": "developer",
        "__end__": END,
    })

    workflow.add_conditional_edges("developer", router, {
        "qa": "qa",
        "__end__": END,
    })

    # QA decide: passou → FIM, falhou → retry developer
    workflow.add_conditional_edges("qa", should_retry, {
        "developer": "developer",
        "__end__": END,
    })

    return workflow.compile(checkpointer=checkpointer)
