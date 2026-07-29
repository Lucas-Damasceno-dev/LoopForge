"""
Grafo LangGraph: StateGraph, router condicional, build_graph.
Centraliza toda a lógica de roteamento (evita acoplamento com dispatcher/iteration).
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph

from .nodes.appsec import appsec
from .nodes.cpo import cpo
from .nodes.developer import developer
from .nodes.devops import devops
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
        print("--- ROTEAMENTO ADAPTATIVO: Ativando FAST-PATH (Developer -> QA -> AppSec -> DevOps) ---")
        return "developer"

    print("--- ROTEAMENTO ADAPTATIVO: Ativando FULL-PATH (CPO -> PM -> Tech Lead -> Dev -> QA -> AppSec -> DevOps) ---")
    return "cpo"


def router(
    state: GraphState,
) -> str:
    """Router único: decide próximo nó baseado no estado."""
    next_agent = state.get("next_agent", "cpo")

    if next_agent in ("FINISH", "__end__", None):
        return END

    if next_agent in ("cpo", "pm", "tech_lead", "developer", "qa", "appsec", "devops"):
        return next_agent

    # Fallback seguro: se next_agent for desconhecido ou FINISH, encerra o fluxo
    return END


def should_retry(state: GraphState) -> Literal["appsec", "developer", "__end__"]:
    """Decide após QA se deve prosseguir para AppSec ou retentar."""
    test_report = state.get("test_report", {})
    tests_failed = test_report.get("summary", {}).get("tests_failed", 1)
    qa_attempt = state.get("qa_attempt_count", 0)
    max_retries = state.get("max_retries", 3)

    if tests_failed == 0:
        return "appsec"

    if qa_attempt < max_retries:
        return "developer"

    return END


def build_graph(
    checkpointer: InMemorySaver | None = None,
    interrupt_after: list[str] | None = None,
    human_gate_enabled: bool = False,
):
    """Constrói e compila o grafo com checkpointing, roteamento adaptativo e human-in-the-loop opcional."""
    workflow = StateGraph(GraphState)

    # Adiciona nós (Pipeline completo de 7 agentes: CPO, PM, Tech Lead, Dev, QA, AppSec, DevOps)
    workflow.add_node("cpo", cpo)
    workflow.add_node("pm", product_manager)
    workflow.add_node("tech_lead", tech_lead)
    workflow.add_node("developer", developer)
    workflow.add_node("qa", qa)
    workflow.add_node("appsec", appsec)
    workflow.add_node("devops", devops)

    # Entry point condicional — Roteamento adaptativo (Fast-Path vs Full-Path)
    workflow.set_conditional_entry_point(
        entry_router,
        {
            "cpo": "cpo",
            "developer": "developer",
        },
    )

    # Arestas condicionais — Roteamento centralizado
    workflow.add_conditional_edges(
        "cpo",
        router,
        {
            "pm": "pm",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "pm",
        router,
        {
            "tech_lead": "tech_lead",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "tech_lead",
        router,
        {
            "developer": "developer",
            "__end__": END,
        },
    )

    workflow.add_conditional_edges(
        "developer",
        router,
        {
            "qa": "qa",
            "__end__": END,
        },
    )

    # QA decide: passou → appsec, falhou → retry developer
    workflow.add_conditional_edges(
        "qa",
        should_retry,
        {
            "appsec": "appsec",
            "developer": "developer",
            "__end__": END,
        },
    )

    # AppSec decide: passou → devops, falhou → retry developer
    workflow.add_conditional_edges(
        "appsec",
        router,
        {
            "devops": "devops",
            "developer": "developer",
            "__end__": END,
        },
    )

    # DevOps -> FIM
    workflow.add_conditional_edges(
        "devops",
        router,
        {
            "__end__": END,
        },
    )

    # Se human_gate_enabled, pausa após developer/qa/appsec para aprovação manual
    gates = list(interrupt_after) if interrupt_after else []
    if human_gate_enabled:
        for n in ("developer", "qa", "appsec"):
            if n not in gates:
                gates.append(n)

    return workflow.compile(checkpointer=checkpointer, interrupt_after=gates or None)
