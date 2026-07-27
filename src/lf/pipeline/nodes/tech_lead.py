from lf.pipeline.llm_factory import get_llm
from lf.pipeline.state import GraphState


def tech_lead_node(state: GraphState) -> GraphState:
    us = state.get("user_story_artifact", {})
    feedback = state.get("feedback", "")
    llm = get_llm()
    prompt = f"As Tech Lead, create tech spec for user story {us.get('title')}."
    if feedback:
        prompt += f" Incorporate feedback: {feedback}"

    resp = llm.invoke(prompt)
    text = str(resp.content) if hasattr(resp, "content") else str(resp)

    state["tech_spec"] = f"# Tech Spec\n\n{text}"
    state["current_node"] = "tech_lead"
    history = state.get("history", [])
    history.append("tech_lead")
    state["history"] = history
    return state
