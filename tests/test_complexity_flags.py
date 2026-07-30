"""Testes unitários para as novas flags --mvp e --advanced (complexity_level)."""
from lf.config.schema import TaskSchema
from lf.pipeline.state import GraphState


def test_task_schema_default_complexity():
    task = TaskSchema(id="task-1", title="Test task")
    assert task.complexity_level == "standard"


def test_task_schema_custom_complexity():
    task_mvp = TaskSchema(id="task-1", title="MVP Task", complexity_level="mvp")
    assert task_mvp.complexity_level == "mvp"

    task_adv = TaskSchema(id="task-2", title="Adv Task", complexity_level="advanced")
    assert task_adv.complexity_level == "advanced"


def test_cpo_prompt_complexity_injection():
    from lf.pipeline.nodes.cpo import cpo
    state: GraphState = {
        "idea": "Build a test app",
        "output_dir": "/tmp",
        "epic": {},
        "user_stories": [],
        "tech_spec": "",
        "code": "",
        "test_report": {},
        "security_review": {},
        "devops_manifest": {},
        "ontology_path": "",
        "project_dir": ".",
        "stack": "python",
        "next_agent": "cpo",
        "attempt_count": 0,
        "qa_attempt_count": 0,
        "appsec_attempt_count": 0,
        "max_retries": 3,
        "error": None,
        "feedback_history": [],
        "mock_llm": True,
        "llm_provider": "google",
        "llm_model_name": "gemini-1.5-flash",
        "llm_temperature": 0.3,
        "is_interactive": False,
        "read_only": False,
        "routing_mode": "full",
        "task_type": "feature",
        "complexity_level": "mvp",
        "expected_schema": None,
        "persona_id": None,
    }
    res = cpo(state)
    assert res["next_agent"] == "pm"
    assert "epic" in res
