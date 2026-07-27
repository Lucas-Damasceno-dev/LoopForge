from lf.config.schema import TaskSchema


class IterationManager:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def should_retry(self, task: TaskSchema) -> bool:
        return task.attempts < task.max_retries and task.status == "failed"

    def prepare_retry(self, task: TaskSchema, feedback: str) -> TaskSchema:
        task.attempts += 1
        task.status = "pending"
        task.prompt = f"{task.prompt}\n[Feedback from attempt {task.attempts}]: {feedback}"
        return task
