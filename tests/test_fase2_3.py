import os

from lf.pipeline.graph import build_graph
from lf.pipeline.state import GraphState
from lf.runner.opencode import OpenCodeRunner


def test_opencode_mock_runner():
    os.environ["OPENCODE_MOCK"] = "1"
    runner = OpenCodeRunner(timeout_seconds=30)
    res = runner.run("Build landing page")
    assert res.exit_code == 0
    assert "MOCK OPENCODE" in res.stdout


def test_graph_router_direct():
    """Test router transitions without invoking LLM."""
    from lf.pipeline.graph import router

    state: GraphState = {
        "idea": "test",
        "output_dir": "/tmp",
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

    # "cpo" é nó de entrada (entry_router), não alvo de EdgeRegistry — router retorna END
    assert router(state) == "__end__"

    state["next_agent"] = "pm"
    assert router(state) == "pm"

    state["next_agent"] = "developer"
    assert router(state) == "developer"

    state["next_agent"] = "qa"
    assert router(state) == "qa"

    state["next_agent"] = "FINISH"
    assert router(state) == "__end__"


def test_graph_builds():
    """Verifica que o grafo compila sem erros."""
    graph = build_graph(checkpointer=None)
    assert graph is not None
    # Verifica que tem os nós esperados
    assert "cpo" in graph.nodes
    assert "pm" in graph.nodes
    assert "tech_lead" in graph.nodes
    assert "developer" in graph.nodes
    assert "qa" in graph.nodes
