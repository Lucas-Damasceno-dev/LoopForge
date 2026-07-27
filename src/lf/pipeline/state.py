from typing import Any, Optional, TypedDict


class GraphState(TypedDict, total=False):
    project_id: str
    task_id: str
    prompt: str
    status: str
    attempts: int
    max_retries: int
    feedback: Optional[str]
    epic_artifact: Optional[dict[str, Any]]
    user_story_artifact: Optional[dict[str, Any]]
    tech_spec: Optional[str]
    opencode_stdout: Optional[str]
    test_report: Optional[dict[str, Any]]
    error: Optional[str]
    current_node: str
    history: list[str]
