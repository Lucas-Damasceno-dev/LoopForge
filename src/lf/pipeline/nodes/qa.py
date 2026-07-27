from lf.pipeline.state import GraphState


def qa_node(state: GraphState) -> GraphState:
    opencode_stdout = state.get("opencode_stdout", "")
    error = state.get("error", None)

    if error:
        state["test_report"] = {
            "total_tests": 1,
            "passed": 0,
            "failed": 1,
            "error": error,
        }
        state["status"] = "failed"
    else:
        state["test_report"] = {
            "total_tests": 1,
            "passed": 1,
            "failed": 0,
        }
        state["status"] = "done"

    state["current_node"] = "qa"
    history = state.get("history", [])
    history.append("qa")
    state["history"] = history
    return state
