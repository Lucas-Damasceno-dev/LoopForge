from lf.pipeline.llm_factory import get_llm
from lf.pipeline.state import GraphState


def pm_node(state: GraphState) -> GraphState:
    epic = state.get("epic_artifact", {})
    llm = get_llm()
    resp = llm.invoke(f"As PM, convert Epic {epic.get('title')} into User Story JSON artifact")
    text = str(resp.content) if hasattr(resp, "content") else str(resp)

    state["user_story_artifact"] = {
        "id": f"us-{state.get('task_id', '1')}",
        "title": f"User Story for {epic.get('title', 'feature')}",
        "acceptance_criteria": ["Implementation matches requirements", text[:100]],
    }
    state["current_node"] = "pm"
    history = state.get("history", [])
    history.append("pm")
    state["history"] = history
    return state
