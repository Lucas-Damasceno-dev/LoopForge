from typing import Any
from lf.pipeline.llm_factory import get_llm
from lf.pipeline.state import GraphState


def cpo_node(state: GraphState) -> GraphState:
    prompt = state.get("prompt", "Default task description")
    llm = get_llm()
    resp = llm.invoke(f"As CPO, generate an Epic JSON artifact for prompt: {prompt}")
    text = str(resp.content) if hasattr(resp, "content") else str(resp)

    state["epic_artifact"] = {
        "id": f"epic-{state.get('task_id', '1')}",
        "title": f"Epic for {prompt[:30]}",
        "description": text,
    }
    state["current_node"] = "cpo"
    history = state.get("history", [])
    history.append("cpo")
    state["history"] = history
    return state
