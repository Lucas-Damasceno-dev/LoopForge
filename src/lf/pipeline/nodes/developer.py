from lf.pipeline.state import GraphState
from lf.runner.opencode import OpenCodeRunner


def developer_node(state: GraphState) -> GraphState:
    tech_spec = state.get("tech_spec", "")
    prompt = f"Implement feature according to tech spec:\n{tech_spec}"

    runner = OpenCodeRunner(timeout_seconds=300)
    result = runner.run(prompt=prompt)

    state["opencode_stdout"] = result.stdout
    state["attempts"] = state.get("attempts", 0) + 1

    if result.exit_code != 0:
        state["error"] = result.stderr or f"OpenCode exit code {result.exit_code}"

    state["current_node"] = "developer"
    history = state.get("history", [])
    history.append("developer")
    state["history"] = history
    return state
