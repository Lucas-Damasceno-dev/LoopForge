from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, Field

from lf.config.schema import TaskSchema
from lf.guardrails.circuit_breaker import CircuitBreaker
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.llm_factory import SQLiteLLMCache
from lf.runner.opencode.llm import call_llm_via_opencode


class SimpleSchema(BaseModel):
    title: str = Field(..., description="Title")


def test_call_llm_via_opencode_cache(tmp_path):
    cache = SQLiteLLMCache(db_path=tmp_path / "cache.sqlite")
    full_prompt = "System prompt\n\nUser prompt"

    # Seed cache
    cache.set(full_prompt, '{"title": "Cached Title"}')

    with patch("lf.runner.opencode.llm.SQLiteLLMCache", return_value=cache):
        # Call with cache hit
        res = call_llm_via_opencode(
            system_prompt="System prompt",
            user_prompt="User prompt",
            schema_model=SimpleSchema,
            cache=True,
        )
        assert res["title"] == "Cached Title"


def test_call_llm_via_opencode_circuit_breaker():
    cb = CircuitBreaker()
    cb.can_proceed = MagicMock(return_value=False)

    with pytest.raises(RuntimeError, match="Circuit breaker is open"):
        call_llm_via_opencode(
            system_prompt="System",
            user_prompt="User",
            circuit_breaker=cb,
        )


def test_task_dispatcher_human_interrupt_handler(tmp_path):
    dispatcher = TaskDispatcher(interactive=True)
    snapshot = MagicMock()
    snapshot.next = ["developer"]
    snapshot.values = {"tech_spec": "Sample Tech Spec text"}

    config = {"configurable": {"thread_id": "test"}}
    app = MagicMock()

    # Test choice 'c' (continue)
    with patch("builtins.input", return_value="c"):
        assert dispatcher._human_interrupt_handler(snapshot, config, app) is True

    # Test choice 'r' (retry)
    with patch("builtins.input", return_value="r"):
        assert dispatcher._human_interrupt_handler(snapshot, config, app) is True

    # Test choice 'a' (adjust)
    with patch("builtins.input", side_effect=["a", "New prompt feedback"]):
        assert dispatcher._human_interrupt_handler(snapshot, config, app) is True

    # Test choice 'x' (abort)
    with patch("builtins.input", return_value="x"):
        assert dispatcher._human_interrupt_handler(snapshot, config, app) is False


def test_task_dispatcher_create_pr_with_labels(tmp_path):
    dispatcher = TaskDispatcher()
    task = TaskSchema(id="T-001", title="Test Task", persona="developer")
    final_state = {"test_report": {"summary": {"tests_failed": 0}}}

    with patch("lf.orchestrator.task_dispatcher.GitCheckpointManager"), patch(
        "lf.orchestrator.task_dispatcher.create_github_pr"
    ) as mock_pr:
        dispatcher._create_pr_with_labels(task, final_state, project_id="proj1")
        assert mock_pr.called is True

