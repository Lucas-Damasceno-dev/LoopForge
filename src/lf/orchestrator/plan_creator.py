from lf.config.schema import PlanSchema, TaskSchema


def create_plan_from_vision(vision_text: str) -> PlanSchema:
    """Generates a Task DAG plan based on high-level project vision."""
    t1 = TaskSchema(
        id="task-1",
        title="Setup project scaffolding and architecture",
        prompt=f"Initialize baseline repository setup for: {vision_text}",
        agent_id="cpo",
        depends_on=[],
    )
    t2 = TaskSchema(
        id="task-2",
        title="Implement core functionality and models",
        prompt=f"Build core features for: {vision_text}",
        agent_id="developer",
        depends_on=["task-1"],
    )
    t3 = TaskSchema(
        id="task-3",
        title="Verification, test suite execution, and docs",
        prompt=f"Verify and document feature implementation for: {vision_text}",
        agent_id="qa",
        depends_on=["task-2"],
    )
    return PlanSchema(
        tasks=[t1, t2, t3],
        graph={
            "task-1": ["task-2"],
            "task-2": ["task-3"],
            "task-3": [],
        },
    )
