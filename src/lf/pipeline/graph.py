"""
Grafo LangGraph: StateGraph, router condicional, build_graph.
Centraliza toda a lógica de roteamento (evita acoplamento com dispatcher/iteration).
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from .nodes.cpo import cpo
from .nodes.developer import developer
from .nodes.pm import product_manager
from .nodes.qa import qa
from .nodes.tech_lead import tech_lead
from .state import GraphState


# --- Router Centralizado ---
# Toda decisão de roteamento está AQUI, não no dispatcher nem no iteration_manager.
def entry_router(state: GraphState) -> Literal["cpo", "developer"]:
    """Decide o nó de entrada inicial (Fast-Path vs Full-Path)."""
    routing_mode = state.get("routing_mode", "full")
    task_type = state.get("task_type", "feature")

    # Fast-Path: pula CPO, PM e Tech Lead para tarefas rápidas, bugs ou refatorações
    if routing_mode == "fast" or task_type in ("fast", "bugfix", "refactor", "simple"):
        print("--- ROTEAMENTO ADAPTATIVO: Ativando FAST-PATH (Developer -> QA) ---")
        return "developer"

    print("--- ROTEAMENTO ADAPTATIVO: Ativando FULL-PATH (CPO -> PM -> Tech Lead -> Dev -> QA) ---")
    return "cpo"


def router(state: GraphState) -> Literal["cpo", "pm", "tech_lead",
                                          "developer", "qa", "__end__"]:
    """Router único: decide próximo nó baseado no estado."""
    next_agent = state.get("next_agent", "cpo")
    attempt = state.get("attempt_count", 0)
    max_retries = state.get("max_retries", 3)

    if next_agent == "FINISH":
        return END

    if next_agent in ("cpo", "pm", "tech_lead", "developer", "qa"):
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


def build_graph(
    checkpointer: InMemorySaver | None = None,
    interrupt_after: list[str] | None = None,
    human_gate_enabled: bool = False,
):
    """Constrói e compila o grafo com checkpointing, roteamento adaptativo e human-in-the-loop opcional.

    Args:
        checkpointer: SqliteSaver para checkpoint/persistência.
        interrupt_after: Lista de nós que devem pausar para aprovação humana.
        human_gate_enabled: Se True, adiciona nó de gate humano após developer/qa.
    """
    workflow = StateGraph(GraphState)

    # Adiciona nós
    workflow.add_node("cpo", cpo)
    workflow.add_node("pm", product_manager)
    workflow.add_node("tech_lead", tech_lead)
    workflow.add_node("developer", developer)
    workflow.add_node("qa", qa)

    # Entry point condicional — Roteamento adaptativo (Fast-Path vs Full-Path)
    workflow.set_conditional_entry_point(entry_router, {
        "cpo": "cpo",
        "developer": "developer",
    })

    # Arestas condicionais — Roteamento centralizado
    workflow.add_conditional_edges("cpo", router, {
        "pm": "pm",
        "__end__": END,
    })

    workflow.add_conditional_edges("pm", router, {
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

    # Se human_gate_enabled, pausa após developer e qa para aprovação manual
    gates = list(interrupt_after) if interrupt_after else []
    if human_gate_enabled:
        for n in ("developer", "qa"):
            if n not in gates:
                gates.append(n)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=gates or None)

