from typing import Any
from lf.config.schema import TaskSchema
from lf.pipeline.graph import build_pipeline_graph
from lf.pipeline.state import GraphState


class TaskDispatcher:
    def __init__(self):
        self.graph = build_pipeline_graph()

    def dispatch(self, task: TaskSchema, project_id: str = "project") -> GraphState:
        initial_state: GraphState = {
            "project_id": project_id,
            "task_id": task.id,
            "prompt": task.prompt or task.title,
            "status": "running",
            "attempts": task.attempts,
            "max_retries": task.max_retries,
            "history": [],
        }

        final_state = self.graph.invoke(initial_state)
        return final_state
