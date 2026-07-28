import pytest
from lf.ontology.state_machine.definition import TaskState, PipelineNode
from lf.ontology.state_machine.labels import get_git_label, STATE_LABELS


def test_task_state_and_pipeline_node_enums():
    assert TaskState.PENDING.value == "pending"
    assert TaskState.DONE.value == "done"
    assert TaskState.FAILED.value == "failed"

    assert PipelineNode.CPO.value == "cpo"
    assert PipelineNode.DEVELOPER.value == "developer"
    assert PipelineNode.QA.value == "qa"


def test_get_git_label():
    # Test with TaskState enum
    assert get_git_label(TaskState.DONE) == "foundry:status:completed"
    assert get_git_label(TaskState.FAILED) == "foundry:status:failed"
    assert get_git_label(TaskState.RUNNING) == "foundry:status:in-progress"

    # Test with valid string
    assert get_git_label("done") == "foundry:status:completed"
    assert get_git_label("pending") == "foundry:status:pending"

    # Test with custom or invalid string
    assert get_git_label("custom_state") == "foundry:status:custom_state"
