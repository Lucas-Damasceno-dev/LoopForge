"""Testes do NodeFactory data-driven (S2 — CRUD de agentes).

Valida: registro de nós compilados a partir do AgentSchema no NodeRegistry
(key `agent:<slug>`), re-registro idempotente, chamada ao LLM mockado com
prompt/model corretos e slug sanitizado. NUNCA executa LLM real — o
call_llm_via_opencode do módulo é patchado.
"""

import pytest

from lf.api.agents import AgentCreate
from lf.pipeline.graph import NodeRegistry
from lf.pipeline.node_factory import _slugify, compile_agent_node, register_agent_node


def _agent(**overrides) -> AgentCreate:
    data = {"name": "Dev Agent", "prompt": "Você é o agente dev.", "model": "meu-modelo"}
    data.update(overrides)
    return AgentCreate(**data)


def test_slugify_limpo():
    assert _slugify("My Agent!") == "my-agent"
    assert _slugify("Dev Agent") == "dev-agent"
    assert _slugify("  Duplo   Espaco  ") == "duplo-espaco"
    assert _slugify("Upper CASE") == "upper-case"


def test_register_agent_node_key_correta():
    key = register_agent_node(_agent(name="My Agent!"))
    assert key == "agent:my-agent"
    assert key in NodeRegistry.get_all()


def test_re_registro_idempotente():
    key = register_agent_node(_agent(name="Dev Agent"))
    first = NodeRegistry.get_all()[key]
    key2 = register_agent_node(_agent(name="Dev Agent", prompt="novo prompt"))
    assert key2 == key
    assert NodeRegistry.get_all()[key] is not first  # sobrescreve, não duplica
    assert sum(1 for k in NodeRegistry.get_all() if k == key) == 1


def test_node_compilado_chama_llm_com_prompt_e_model(monkeypatch):
    agent = _agent(model="meu-modelo", temperature=0.9)
    calls: list[dict] = []

    def fake_llm(**kwargs):
        calls.append(kwargs)
        return "resposta do agente"

    monkeypatch.setattr("lf.pipeline.node_factory.call_llm_via_opencode", fake_llm)

    node = compile_agent_node(agent)
    state = {"llm_model_name": "meu-modelo", "project_dir": "/tmp", "extra": 1}
    out = node(state)

    assert len(calls) == 1
    assert calls[0]["system_prompt"] == "Você é o agente dev."
    assert calls[0]["model"] == "meu-modelo"
    assert calls[0]["temperature"] == 0.9
    assert calls[0]["node"] == "agent:dev-agent"

    # Formato do nó real (appsec): spread do state + patch com next_agent.
    assert out["next_agent"] == "FINISH"
    assert out["agent_output"] == "resposta do agente"
    assert out["extra"] == 1  # spread preservado
    assert out["llm_model_name"] == "meu-modelo"


def test_node_mock_llm_flag_repassado(monkeypatch):
    calls: list[dict] = []

    def fake_llm(**kwargs):
        calls.append(kwargs)
        return "mock"

    monkeypatch.setattr("lf.pipeline.node_factory.call_llm_via_opencode", fake_llm)

    node = compile_agent_node(_agent())
    node({"mock_llm": True})
    assert calls[0]["mock"] is True

    node({"mock_llm": False})
    assert calls[1]["mock"] is False


def test_node_uma_chamada_em_sucesso(monkeypatch):
    """Retry não é implementado no nó (responsabilidade do grafo) — chamada
    bem-sucedida dispara exatamente 1 invocação do LLM."""
    calls: list[dict] = []

    def fake_llm(**kwargs):
        calls.append(kwargs)
        return "ok"

    monkeypatch.setattr("lf.pipeline.node_factory.call_llm_via_opencode", fake_llm)

    node = compile_agent_node(_agent(max_retries=5))
    node({})
    assert len(calls) == 1


def test_register_retorna_funcao_compilada():
    agent = _agent(name="Compiled")
    key = register_agent_node(agent)
    assert callable(NodeRegistry.get_all()[key])
