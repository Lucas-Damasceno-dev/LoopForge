from typing import Any
from lf.config.schema import TaskSchema
from lf.pipeline.graph import build_graph
from lf.pipeline.state import GraphState
from lf.ontology.state_machine.labels import get_git_label
from lf.ontology.state_machine.definition import TaskState
from lf.runner.git.pr import create_github_pr
from lf.runner.git.checkpoint import GitCheckpointManager


class TaskDispatcher:
    def __init__(self, mock_llm: bool = True):
        self.graph = build_graph(checkpointer=None)
        self.mock_llm = mock_llm

    def _build_initial_state(self, task: TaskSchema, project_id: str) -> GraphState:
        return {
            "idea": task.title,
            "output_dir": f"/tmp/loopforge/{project_id}",
            "epic": {},
            "user_stories": [],
            "tech_spec": "",
            "code": "",
            "test_report": {},
            "ontology_path": "examples/the-foundry",
            "project_dir": ".",
            "stack": "python",
            "next_agent": "cpo",
            "attempt_count": task.attempts,
            "max_retries": task.max_retries,
            "error": None,
            "feedback_history": [],
            "mock_llm": self.mock_llm,
            "llm_provider": "google",
            "llm_model_name": "gemini-2.0-flash",
            "llm_temperature": 0.3,
            "is_interactive": False,
            "expected_schema": None,
            "persona_id": task.agent_id,
        }

    def _create_pr_with_labels(self, task: TaskSchema, final_state: dict, project_id: str):
        """Cria PR com labels do Foundry ao final da execução."""
        test_report = final_state.get("test_report", {})
        tests_failed = test_report.get("summary", {}).get("tests_failed", 1)
        success = tests_failed == 0 and not final_state.get("error")

        state = TaskState.DONE if success else TaskState.FAILED
        labels = [get_git_label(state)]

        title = f"[LoopForge] {task.title}"
        body = (
            f"## Task: {task.title}\n\n"
            f"**Status:** {state.value}\n"
            f"**Agent:** {task.agent_id}\n"
            f"**Tests Failed:** {tests_failed}\n"
        )

        # Cria checkpoint git + PR (não bloqueia se falhar)
        try:
            GitCheckpointManager().create_checkpoint(f"loopforge/task-{project_id}")
            create_github_pr(title=title, body=body, labels=labels)
        except Exception:
            pass  # PR é bônus, não crítica

    def dispatch(self, task: TaskSchema, project_id: str = "project") -> dict:
        initial_state = self._build_initial_state(task, project_id)

        try:
            final_state = self.graph.invoke(initial_state)
            result = dict(final_state) if isinstance(final_state, dict) else dict(final_state)

            # Cria PR com labels do Foundry
            self._create_pr_with_labels(task, result, project_id)

            return result
        except Exception as e:
            return {**initial_state, "error": str(e), "status": "failed"}
