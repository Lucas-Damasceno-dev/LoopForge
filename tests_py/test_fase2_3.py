import os
from lf.pipeline.graph import build_pipeline_graph
from lf.runner.opencode import OpenCodeRunner


def test_opencode_mock_runner():
    os.environ["OPENCODE_MOCK"] = "1"
    runner = OpenCodeRunner()
    res = runner.run("Build landing page")
    assert res.exit_code == 0
    assert "MOCK OPENCODE" in res.stdout


def test_pipeline_graph_execution():
    os.environ["OPENCODE_MOCK"] = "1"
    graph = build_pipeline_graph()
    initial_state = {
        "project_id": "test_proj",
        "task_id": "task-100",
        "prompt": "Create user login system",
        "attempts": 0,
        "max_retries": 3,
        "history": [],
    }

    final_state = graph.invoke(initial_state)
    assert final_state.get("status") == "done"
    assert "cpo" in final_state.get("history", [])
    assert "qa" in final_state.get("history", [])
