import os

import pytest

from lf.orchestrator.plan_creator import create_plan_from_vision
from lf.pipeline.graph import build_graph
from lf.pipeline.llm_factory import (
    DEFAULT_OPENROUTER_MODEL,
    call_openrouter_api,
)


def test_adaptive_routing_full_path():
    """Testa se o modo full ativa a entrada no nó CPO (Full-Path)."""
    graph = build_graph()
    state = {
        "idea": "Criar sistema de tarefas",
        "routing_mode": "full",
        "task_type": "feature",
        "mock_llm": True,
    }
    # Compilado deve rodar CPO -> PM -> Tech Lead -> Dev -> QA -> END
    result = graph.invoke(state)
    assert result.get("epic") is not None
    assert result.get("next_agent") in ("qa", "FINISH")


def test_adaptive_routing_fast_path():
    """Testa se o modo fast ativa o Fast-Path (direto no Developer -> QA)."""
    graph = build_graph()
    state = {
        "idea": "Corrigir bug na função de cálculo de impostos",
        "routing_mode": "fast",
        "task_type": "bugfix",
        "mock_llm": True,
    }
    # No Fast-Path, pula CPO/PM/Tech Lead e vai direto para Developer -> QA
    result = graph.invoke(state)
    assert result.get("code") is not None
    assert not result.get("epic")  # CPO não rodou


def test_plan_creator_fast_path():
    """Testa se o gerador de plano respeita o modo fast-path."""
    plan_full = create_plan_from_vision("Criar app", output_dir="/tmp/test_plan", routing_mode="full")
    assert len(plan_full.tasks) == 5

    plan_fast = create_plan_from_vision("Fix bug", output_dir="/tmp/test_plan", routing_mode="fast")
    assert len(plan_fast.tasks) == 2
    assert plan_fast.tasks[0]["persona"] == "developer"
    assert plan_fast.tasks[1]["persona"] == "qa"


def test_openrouter_api_real_ling_flash():
    """Testa chamada real à API do OpenRouter se a chave estiver definida no ambiente."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        pytest.skip("OPENROUTER_API_KEY não configurada no ambiente")

    prompt = "Responda apenas com a palavra 'SUCCESS' em letras maiúsculas."
    res = call_openrouter_api(prompt=prompt, model=DEFAULT_OPENROUTER_MODEL, api_key=key, timeout=20.0)
    assert "SUCCESS" in res.upper()

