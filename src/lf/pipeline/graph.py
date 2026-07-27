from typing import Literal
from langgraph.graph import END, StateGraph

from lf.pipeline.nodes.cpo import cpo_node
from lf.pipeline.nodes.developer import developer_node
from lf.pipeline.nodes.pm import pm_node
from lf.pipeline.nodes.qa import qa_node
from lf.pipeline.nodes.tech_lead import tech_lead_node
from lf.pipeline.state import GraphState


def router(state: GraphState) -> Literal["cpo", "pm", "tech_lead", "developer", "qa", "__end__"]:
    current = state.get("current_node", "")
    status = state.get("status", "pending")
    attempts = state.get("attempts", 0)
    max_retries = state.get("max_retries", 3)

    if not current:
        return "cpo"
    elif current == "cpo":
        return "pm"
    elif current == "pm":
        return "tech_lead"
    elif current == "tech_lead":
        return "developer"
    elif current == "developer":
        return "qa"
    elif current == "qa":
        if status == "done":
            return END
        elif status == "failed":
            if attempts < max_retries:
                state["feedback"] = f"Retry attempt {attempts + 1} after QA failure: {state.get('error')}"
                return "developer"
            return END

    return END


def build_pipeline_graph():
    builder = StateGraph(GraphState)

    builder.add_node("cpo", cpo_node)
    builder.add_node("pm", pm_node)
    builder.add_node("tech_lead", tech_lead_node)
    builder.add_node("developer", developer_node)
    builder.add_node("qa", qa_node)

    builder.set_entry_point("cpo")

    builder.add_conditional_edges("cpo", router)
    builder.add_conditional_edges("pm", router)
    builder.add_conditional_edges("tech_lead", router)
    builder.add_conditional_edges("developer", router)
    builder.add_conditional_edges("qa", router)

    return builder.compile()
