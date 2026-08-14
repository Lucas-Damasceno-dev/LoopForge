"""Validador semântico de pipelines (S3 — editor de pipelines).

Validação de grafo (não de shape pydantic): referências de arestas, teto de
retry (doom-loop guard), agentes conhecidos, input/output explícitos, ciclos,
nós órfãos, split/merge e dead-ends. Mensagens em EN, uma por violação.

Usado pelo endpoint POST /api/v1/pipelines/{id}/validate (pipelines.py) e
reusado pela task 4 (execução de pipelines). Importa apenas schemas pydantic
de pipelines.py — o endpoint faz import local aqui (evita import circular).
"""

from lf.api.pipelines import PipelineBase

# Agentes do pipeline nativo (regras de negócio do LoopForge) — aceitos em
# pipelines mesmo sem registro em agent_templates (biblioteca de agentes).
SPECIAL_AGENT_IDS = {
    "cpo",
    "pm",
    "tech_lead",
    "test_writer",
    "developer",
    "qa",
    "appsec",
    "devops",
    "parallel_audit",
}


def _cycle_detected(nodes: list, edges: list) -> bool:
    """Detecta ciclo considerando apenas edges não-retry.

    Retry edges são auto/back-edges de re-tentativa — teto garantido por
    max_retries >= 1 (regra acima). Removê-las do grafo de detecção equivale
    a permitir ciclos que contenham >= 1 edge retry e pegar apenas ciclos
    "reais" (sem retry). DFS iterativo com cores (white/gray/black).
    """
    node_ids = {n.id for n in nodes}
    adj = {
        nid: [e.target for e in edges if e.source == nid and e.type != "retry" and e.target in node_ids]
        for nid in node_ids
    }
    color = {nid: "white" for nid in node_ids}
    for start in node_ids:
        if color[start] != "white":
            continue
        stack = [(start, iter(adj[start]))]
        color[start] = "gray"
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if color[nxt] == "gray":
                    return True  # back-edge → ciclo sem retry
                if color[nxt] == "white":
                    color[nxt] = "gray"
                    stack.append((nxt, iter(adj[nxt])))
                    advanced = True
                    break
            if not advanced:
                color[node] = "black"
                stack.pop()
    return False


def _orphan_nodes(nodes: list, edges: list) -> list[str]:
    """Nós inalcançáveis a partir do input (BFS, considerando todas as edges)."""
    node_ids = {n.id for n in nodes}
    inputs = [n.id for n in nodes if n.type == "input"]
    if not inputs:
        return []
    start = inputs[0]
    adj = {nid: [e.target for e in edges if e.source == nid] for nid in node_ids}
    seen = {start}
    queue = [start]
    while queue:
        cur = queue.pop(0)
        for nxt in adj.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)
    return sorted(node_ids - seen)


def validate_pipeline(pipeline: PipelineBase, known_agents: set[str]) -> list[str]:
    """Valida um pipeline. Retorna lista de erros (vazia = válido)."""
    errors: list[str] = []

    if pipeline is None:
        return ["pipeline is required"]

    nodes = pipeline.nodes
    edges = pipeline.edges

    if not nodes:
        errors.append("pipeline has no nodes")
    if not edges:
        errors.append("pipeline has no edges")
    if not nodes or not edges:
        return errors

    node_ids = {n.id for n in nodes}

    # 1. Referências de arestas
    for e in edges:
        if e.source not in node_ids:
            errors.append(f"edge references unknown source node: {e.source}")
        if e.target not in node_ids:
            errors.append(f"edge references unknown target node: {e.target}")

    # 2. Semântica de aresta
    for e in edges:
        if e.type == "conditional" and (not e.condition or not e.condition.strip()):
            errors.append(f"conditional edge requires non-empty condition: {e.source} -> {e.target}")
        if e.type == "retry" and e.max_retries < 1:
            errors.append(f"retry edge requires max_retries >= 1: {e.source} -> {e.target}")

    # 3. Agentes conhecidos (biblioteca do DB + ids especiais do pipeline nativo)
    for n in nodes:
        if n.type != "agent":
            continue
        if not n.agent_id:
            errors.append(f"agent node requires agent_id: {n.id}")
        elif n.agent_id not in known_agents and n.agent_id not in SPECIAL_AGENT_IDS:
            errors.append(f"agent node references unknown agent: {n.id}")

    # 4. Input/output explícitos (v1 — exigimos declarados)
    inputs = [n for n in nodes if n.type == "input"]
    outputs = [n for n in nodes if n.type == "output"]
    if not inputs:
        errors.append("pipeline requires at least one input node")
    if not outputs:
        errors.append("pipeline requires at least one output node")

    # 5. Ciclo não-retry
    if _cycle_detected(nodes, edges):
        errors.append("cycle detected (non-retry)")

    # 6. Órfãos (só valida se há input — sem input já é erro acima)
    for orphan in _orphan_nodes(nodes, edges):
        errors.append(f"orphan node not reachable from input: {orphan}")

    # 7. Split/merge estruturais
    for n in nodes:
        outgoing = [e for e in edges if e.source == n.id]
        incoming = [e for e in edges if e.target == n.id]
        if n.type == "split" and len(outgoing) < 2:
            errors.append(f"split requires >=2 outgoing edges: {n.id}")
        if n.type == "merge" and len(incoming) < 2:
            errors.append(f"merge requires >=2 incoming edges: {n.id}")

    # 8. Dead-ends: todo nó (exceto output) precisa de saída (gate incluído)
    for n in nodes:
        outgoing = [e for e in edges if e.source == n.id]
        if n.type != "output" and not outgoing:
            errors.append(f"node has no outgoing edges and is not output: {n.id}")

    return errors
