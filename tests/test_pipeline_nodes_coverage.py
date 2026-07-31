from unittest.mock import patch

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.nodes.cpo import _mock_epic, cpo
from lf.pipeline.nodes.developer import developer
from lf.pipeline.nodes.pm import _mock_stories, product_manager
from lf.pipeline.nodes.qa import qa
from lf.pipeline.nodes.tech_lead import tech_lead


def test_cpo_node(tmp_path):
    # Mock mode
    state = {"idea": "Nova ideia", "mock_llm": True, "output_dir": str(tmp_path)}
    res = cpo(state)
    assert res["next_agent"] == "pm"
    assert "epic" in res

    # Reuse existing epic
    res_reuse = cpo(res)
    assert res_reuse["next_agent"] == "pm"

    # LLM call via OpenRouter/OpenCode mock
    with patch("lf.pipeline.nodes.cpo.call_llm_via_opencode") as mock_call:
        mock_call.return_value = _mock_epic("Ideia via LLM")
        res_llm = cpo({"idea": "Ideia via LLM", "mock_llm": False, "output_dir": str(tmp_path)})
        assert res_llm["next_agent"] == "pm"


def test_pm_node(tmp_path):
    epic = _mock_epic("Test Epic")

    # Mock mode
    state = {"epic": epic, "mock_llm": True, "output_dir": str(tmp_path)}
    res = product_manager(state)
    assert res["next_agent"] == "tech_lead"
    assert "user_stories" in res

    # Reuse existing stories
    res_reuse = product_manager(res)
    assert res_reuse["next_agent"] == "tech_lead"

    # LLM call via mock
    with patch("lf.pipeline.nodes.pm.call_llm_via_opencode") as mock_call:
        mock_call.return_value = {"stories": _mock_stories(epic)}
        res_llm = product_manager({"epic": epic, "mock_llm": False, "output_dir": str(tmp_path)})
        assert res_llm["next_agent"] == "tech_lead"


def test_tech_lead_node(tmp_path):
    user_stories = _mock_stories(_mock_epic("Test"))

    # Mock mode
    state = {"user_stories": user_stories, "mock_llm": True, "output_dir": str(tmp_path)}
    res = tech_lead(state)
    assert res["next_agent"] == "test_writer"
    assert "tech_spec" in res

    # Reuse existing spec
    res_reuse = tech_lead(res)
    assert res_reuse["next_agent"] == "test_writer"



def test_developer_node(tmp_path):
    state = {
        "tech_spec": "# Spec\nImplement function",
        "mock_llm": True,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res = developer(state)
    assert res["next_agent"] == "qa"
    assert "code" in res


def test_qa_node(tmp_path):
    state = {
        "code": "print('hello')",
        "mock_llm": True,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res = qa(state)
    assert "test_report" in res


def test_task_dispatcher(tmp_path):
    task = TaskSchema(
        id="T-001",
        title="Test Task",
        persona="developer",
        routing_mode="fast",
    )
    dispatcher = TaskDispatcher(mock_llm=True, interactive=False)
    with patch.object(dispatcher, "_create_pr_with_labels"):
        result = dispatcher.dispatch(task, project_id="test_proj")
        assert result is not None
