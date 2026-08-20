"""Construção de grafo de dependências via NetworkX e cálculo de estabilidade/ciclos."""

from typing import Any, List

try:
    import networkx as nx
except ImportError:
    nx = None  # type: ignore

from genome.store.models import ModuleInfo


def build_dependency_graph(modules: List[ModuleInfo]) -> Any:
    if nx is None:
        return None
    G = nx.DiGraph()
    for mod in modules:
        G.add_node(mod.path)
        for dep in mod.dependencies:
            G.add_edge(mod.path, dep)
    return G


def compute_metrics(graph: Any, modules: List[ModuleInfo]) -> List[ModuleInfo]:
    if graph is None:
        return modules
    mod_map = {m.path: m for m in modules}

    for path, mod in mod_map.items():
        # Dependências de saída (fan-out)
        out_degree = graph.out_degree(path) if hasattr(graph, "has_node") and graph.has_node(path) else 0
        # Dependentes de entrada (fan-in)
        in_degree = graph.in_degree(path) if hasattr(graph, "has_node") and graph.has_node(path) else 0

        # Mapear dependentes
        dependents = list(graph.predecessors(path)) if hasattr(graph, "has_node") and graph.has_node(path) else []
        mod.dependents = sorted(dependents)

        # Instabilidade I = Ce / (Ca + Ce) = out_degree / (in_degree + out_degree)
        total = in_degree + out_degree
        if total > 0:
            mod.instability = round(out_degree / total, 2)
        else:
            mod.instability = 0.0

    return list(mod_map.values())


def detect_circular_dependencies(graph: Any) -> List[List[str]]:
    if graph is None or nx is None:
        return []
    try:
        cycles = list(nx.simple_cycles(graph))
        return [c for c in cycles if len(c) > 1]
    except Exception:
        return []
