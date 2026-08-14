"""NodeFactory data-driven (S2 — CRUD de agentes).

Compila um nó LangGraph genérico a partir de um AgentSchema pydantic
(lf.api.agents.AgentBase) e o registra no NodeRegistry sob a key
`agent:<slug>` (slug = name sanitizado kebab).

O nó compilado segue o padrão dos nós reais (ex.: nodes/appsec.py):
- assinatura síncrona ``def node(state, config=None) -> dict``;
- resolve o modelo via ``resolve_model(state)`` (override por run em
  ``state["llm_model_name"]`` vence);
- prompt efetivo via ``get_effective_prompt("agent:<slug>", agent.prompt)``
  (override persistido vence o prompt do agente);
- chama ``call_llm_via_opencode`` (mesmo primitivo dos nós atuais, mockável
  via ``state["mock_llm"]``);
- retorna o spread do state + patch mínimo no formato dos nós reais
  (``next_agent`` / ``agent_output``).

Retry e timeout: NÃO são implementados no nó. O repo não expõe mecanismo de
retry no nível do nó (call_llm_via_opencode não tem retry loop no caminho
subprocesso; o caminho OpenRouter faz retry interno com backoff) e o timeout
de chamada LLM é responsabilidade do runner (OPENCODE_TIMEOUT / config
``runner.subprocess_timeout_seconds``). ``agent.max_retries``/``agent.timeout_seconds``
ficam disponíveis como dados no nó (para uso futuro no grafo/S3), mas não
são aplicados aqui — documentado, não inventado.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig

from lf.api.agents import AgentBase
from lf.pipeline.graph import NodeRegistry
from lf.pipeline.llm_factory import resolve_model
from lf.pipeline.prompt_overrides import get_effective_prompt
from lf.pipeline.state import GraphState
from lf.runner.opencode.llm import call_llm_via_opencode, resolve_run_id


def _slugify(name: str) -> str:
    """Sanitiza o nome do agente para slug kebab: lower, espaços→-, non-alnum→-."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug


def compile_agent_node(agent: AgentBase) -> Callable:
    """Compila uma closure `node(state, config) -> dict` a partir do AgentSchema.

    O retorno espelha o formato dos nós genéricos reais (appsec.py): spread do
    state + patch com `next_agent` e `agent_output`. `next_agent="FINISH"` — o
    router do grafo (graph.router) mapeia destinos desconhecidos para END.
    """
    key = f"agent:{_slugify(agent.name)}"

    def agent_node(state: GraphState, config: Optional[RunnableConfig] = None) -> dict:
        print(f"---EXECUTANDO NÓ: {key}---")

        system_prompt = get_effective_prompt(key, agent.prompt)
        llm_res = call_llm_via_opencode(
            system_prompt=system_prompt,
            user_prompt=state.get("idea", "") or "",
            model=resolve_model(state),
            temperature=agent.temperature,
            mock=state.get("mock_llm", False),
            node=key,
            run_id=resolve_run_id(state, config),
        )
        return {
            **state,
            "agent_output": str(llm_res),
            "next_agent": "FINISH",
        }

    # Dados do agente expostos para o grafo (S3): retry/timeout são política
    # do grafo, não do nó (ver docstring do módulo).
    agent_node.agent_key = key  # type: ignore[attr-defined]
    agent_node.max_retries = agent.max_retries  # type: ignore[attr-defined]
    agent_node.timeout_seconds = agent.timeout_seconds  # type: ignore[attr-defined]
    return agent_node


def register_agent_node(agent: AgentBase) -> str:
    """Compila e registra o nó do agente no NodeRegistry.

    Re-registro com o mesmo key sobrescreve sem erro (NodeRegistry.register é
    atribuição em dict — idempotente). Retorna a key registrada.
    """
    node = compile_agent_node(agent)
    key = node.agent_key  # type: ignore[attr-defined]
    NodeRegistry.register(key, node)
    return key
