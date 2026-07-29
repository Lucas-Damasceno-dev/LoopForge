"""Sistema de plugins para registro e extensibilidade de nós customizados no LoopForge."""
from collections.abc import Callable
from typing import Any

from lf.pipeline.state import GraphState

# Dicionário global de nós customizados
_CUSTOM_NODE_REGISTRY: dict[str, Callable[[GraphState], dict[str, Any]]] = {}


def register_node(name: str, handler: Callable[[GraphState], dict[str, Any]]) -> None:
    """Registra um nó customizado no ecossistema do LoopForge sem necessidade de forkar o repositório.

    Exemplo:
        def my_custom_auditor(state: GraphState) -> dict:
            print("Executando auditoria customizada...")
            return {**state, "next_agent": "developer"}

        import lf
        lf.register_node("custom_auditor", my_custom_auditor)
    """
    if not callable(handler):
        raise ValueError(f"O handler do nó '{name}' deve ser uma função chamável (Callable).")
    _CUSTOM_NODE_REGISTRY[name] = handler
    print(f"--- PLUGIN: Nó customizado '{name}' registrado com sucesso no LoopForge ---")


def unregister_node(name: str) -> None:
    """Remove um nó customizado do registro."""
    _CUSTOM_NODE_REGISTRY.pop(name, None)


def get_registered_nodes() -> dict[str, Callable[[GraphState], dict[str, Any]]]:
    """Retorna dicionário de todos os nós customizados registrados."""
    return dict(_CUSTOM_NODE_REGISTRY)


def clear_registered_nodes() -> None:
    """Limpa o registro de nós de plugins."""
    _CUSTOM_NODE_REGISTRY.clear()
