from unittest.mock import patch

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


def test_dispatcher_emits_failed_event_when_qa_retries_exhausted():
    task = TaskSchema(
        id="T-RETRY-001",
        title="Retry exhausted scenario",
        persona="developer",
        routing_mode="fast",
        max_retries=0,
    )
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)

    with (
        patch.object(dispatcher, "_create_pr_with_labels"),
        patch.object(dispatcher, "_broadcast_ws") as mock_broadcast,
    ):
        result = dispatcher.dispatch(task, project_id="test_retry_fail")

    assert result.get("error")
    assert "QA retries exhausted" in result.get("error")
    assert any(
        call.args[0] == "pipeline_failed"
        and call.args[1] == task.id
        and call.args[2].get("status") == "failed"
        for call in mock_broadcast.call_args_list
    )
