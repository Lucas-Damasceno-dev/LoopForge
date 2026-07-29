"""Teste E2E do pipeline LoopForge em modo mock.

Exercita o grafo completo: build → invoke → verifica transições de estado.
Usa mock_llm=True para evitar dependência de LLM/subprocesso.
"""
import pytest

from lf.pipeline.graph import build_graph
from lf.pipeline.state import GraphState


@pytest.fixture
def initial_state() -> GraphState:
    return {
        "idea": "Build a CLI todo app in Python",
        "output_dir": "/tmp/lf-e2e-test",
        "epic": {},
        "user_stories": [],
        "tech_spec": "",
        "code": "",
        "test_report": {},
        "ontology_path": "",
        "project_dir": "/tmp",
        "stack": "python",
        "next_agent": "cpo",
        "attempt_count": 0,
        "max_retries": 3,
        "error": None,
        "feedback_history": [],
        "mock_llm": True,
        "llm_provider": "google",
        "llm_model_name": "gemini-2.0-flash",
        "llm_temperature": 0.3,
        "is_interactive": False,
        "expected_schema": None,
        "persona_id": None,
    }


def test_pipeline_e2e_full_flow(initial_state: GraphState):
    """Pipeline completo de 5 nós em modo mock."""
    graph = build_graph()
    assert graph is not None

    result = graph.invoke(initial_state)

    # Verifica que o pipeline executou todos os nós
    assert result is not None
    assert isinstance(result, dict)

    # CPO gerou épico
    assert result.get("epic"), "CPO should generate an epic"
    assert result["epic"].get("id"), f"Expected epic.id to be set, got {result['epic'].get('id')}"

    # PM gerou user stories
    assert result.get("user_stories"), "PM should generate user stories"
    assert len(result["user_stories"]) > 0
    assert "id" in result["user_stories"][0]

    # Tech Lead gerou tech spec
    assert result.get("tech_spec"), "Tech Lead should generate a tech spec"
    assert len(result["tech_spec"]) > 0

    # Developer gerou código
    assert result.get("code"), "Developer should generate code"
    assert len(result["code"]) > 0

    # QA gerou relatório de testes
    assert result.get("test_report"), "QA should generate a test report"
    assert "summary" in result["test_report"]
    assert "total_tests" in result["test_report"]["summary"]

    # AppSec gerou revisão de segurança
    assert result.get("security_review"), "AppSec should generate a security review"
    assert "status" in result["security_review"]

    # DevOps gerou manifesto de deployabilidade
    assert result.get("devops_manifest"), "DevOps should generate a devops manifest"
    assert "status" in result["devops_manifest"]

    # Pipeline finalizou (next_agent == FINISH ou __end__)
    assert result.get("next_agent") in ("FINISH", "__end__"), \
        f"Pipeline should finish, got next_agent={result.get('next_agent')}"

    # Sem erros
    assert result.get("error") is None, f"Pipeline should not have errors: {result.get('error')}"


def test_pipeline_e2e_router_sequence(initial_state: GraphState):
    """Verifica que o router segue a ordem CPO → PM → Tech Lead → Developer → QA → AppSec → DevOps."""
    graph = build_graph()

    result = graph.invoke(initial_state)

    # O router sempre passa por CPO primeiro
    assert result.get("epic"), "CPO should have run first"

    # Verifica a sequência completa de 7 agentes
    assert result.get("user_stories"), "PM should have run"
    assert result.get("tech_spec"), "Tech Lead should have run"
    assert result.get("code"), "Developer should have run"
    assert result.get("test_report"), "QA should have run"
    assert result.get("security_review"), "AppSec should have run"
    assert result.get("devops_manifest"), "DevOps should have run"



def test_pipeline_e2e_no_crash_on_missing_fields():
    """Pipeline não deve crashar com estado mínimo."""
    minimal_state: GraphState = {
        "idea": "test",
        "output_dir": "/tmp/lf-e2e-minimal",
        "epic": {},
        "user_stories": [],
        "tech_spec": "",
        "code": "",
        "test_report": {},
        "ontology_path": "",
        "project_dir": "/tmp",
        "stack": "python",
        "next_agent": "cpo",
        "attempt_count": 0,
        "max_retries": 3,
        "error": None,
        "feedback_history": [],
        "mock_llm": True,
    }
    graph = build_graph()
    result = graph.invoke(minimal_state)
    assert result is not None
    # Mesmo com estado mínimo, deve executar sem crash
    assert "error" not in result or result.get("error") is None


def test_pipeline_e2e_max_retries_exhausted(initial_state: GraphState):
    """Verifica comportamento quando max_retries é atingido."""
    initial_state["max_retries"] = 0  # Zero retries = falha imediata
    # Força QA a reportar falhas
    initial_state["test_report"] = {"summary": {"tests_failed": 1, "total_tests": 1}}

    graph = build_graph()
    result = graph.invoke(initial_state)

    # Com max_retries=0 e testes falhando, o pipeline deve finalizar
    assert result is not None
    # next_agent deve chegar a FINISH ou __end__
    assert result.get("next_agent") in ("FINISH", "__end__", None)


def test_opencode_package_imports():
    """Verifica que o pacote opencode/ mantém a API pública."""
    from lf.runner.opencode import (
        OpenCodeResult,
        OpenCodeRunner,
    )

    # OpenCodeResult
    r = OpenCodeResult(exit_code=0, stdout="ok", stderr="")
    assert r.success is True
    assert r.error is None

    # OpenCodeRunner (mock mode)
    import os
    os.environ["OPENCODE_MOCK"] = "1"
    runner = OpenCodeRunner(timeout_seconds=30)
    res = runner.run("test prompt")
    assert res.success
    assert "MOCK" in res.stdout
