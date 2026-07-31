"""Suíte de testes para garantir a integridade dos templates de prompt dos nós da esteira.

Garante que diretrizes críticas de tratamento de erros, documentação,
Clean Architecture e .env.example persistem nos prompts durante refatorações.
"""
from unittest.mock import patch

from lf.pipeline.nodes.developer import developer
from lf.pipeline.nodes.tech_lead import tech_lead


def test_developer_prompt_template_quality_rules(tmp_path):
    """Verifica se o prompt do Developer contém todas as regras obrigatórias de qualidade."""
    state = {
        "idea": "Serviço REST em Rust",
        "stack": "rust",
        "mock_llm": False,
        "output_dir": str(tmp_path),
        "user_stories": [{"id": "US1", "title": "Criar serviço REST"}],
        "tech_spec": "Tech Spec de teste",
    }

    captured_prompts = []

    def mock_call_llm(system_prompt: str, **kwargs):
        captured_prompts.append(system_prompt)
        return "### FILE: src/main.rs\nfn main() {}"

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=mock_call_llm):
        developer(state)

    assert len(captured_prompts) > 0
    dev_prompt = captured_prompts[0]

    # Regra 1.1: Tratamento de erros
    assert "unwrap()" in dev_prompt or "panic!" in dev_prompt or "try/except" in dev_prompt
    assert "TRATAMENTO DE ERROS RIGOROSO" in dev_prompt

    # Regra 1.2: Docstrings obrigatórias
    assert "DOCUMENTAÇÃO OBRIGATÓRIA" in dev_prompt
    assert "docstrings" in dev_prompt

    # Regra 1.4: Módulo de configuração tipado e .env.example
    assert "CONFIGURAÇÃO E AMBIENTE" in dev_prompt
    assert ".env.example" in dev_prompt


def test_tech_lead_prompt_template_clean_architecture(tmp_path):
    """Verifica se o prompt do Tech Lead inclui as diretrizes de Clean Architecture por stack."""
    state = {
        "idea": "Aplicação Web em Python com FastAPI",
        "stack": "python",
        "mock_llm": False,
        "output_dir": str(tmp_path),
        "user_stories": [{"id": "US1", "title": "API FastAPI"}],
    }

    captured_prompts = []

    def mock_call_llm(system_prompt: str, **kwargs):
        captured_prompts.append(system_prompt)
        has_schema = bool(kwargs.get("schema_model"))
        if has_schema and "recommended_stack" in kwargs["schema_model"].__name__.lower():
            return {"recommended_stack": "python", "needs_feedback": False, "approved_stories": ["US1"]}
        return "# Tech Spec Test"

    with patch("lf.pipeline.nodes.tech_lead.call_llm_via_opencode", side_effect=mock_call_llm):
        tech_lead(state)

    assert len(captured_prompts) > 0
    tl_prompts = " ".join(captured_prompts)

    # Regra 1.3: Clean Architecture diretrizes no Tech Lead
    assert "CLEAN ARCHITECTURE POR STACK" in tl_prompts
    assert "src/domain/" in tl_prompts
    assert "src/core/" in tl_prompts
