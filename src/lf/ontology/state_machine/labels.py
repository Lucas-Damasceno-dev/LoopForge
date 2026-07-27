from lf.ontology.state_machine.definition import TaskState


STATE_LABELS: dict[TaskState, str] = {
    TaskState.PENDING: "foundry:status:pending",
    TaskState.RUNNING: "foundry:status:in-progress",
    TaskState.VALIDATING: "foundry:status:validating",
    TaskState.FAILED: "foundry:status:failed",
    TaskState.DONE: "foundry:status:completed",
}


def get_git_label(state: TaskState | str) -> str:
    if isinstance(state, str):
        try:
            state = TaskState(state)
        except ValueError:
            return f"foundry:status:{state}"
    return STATE_LABELS.get(state, "foundry:status:unknown")
