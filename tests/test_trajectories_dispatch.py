"""Testes de integração: dispatch/resume persistem trajetórias em .loopforge/trajectories.db via AsyncSqliteSaver."""

import os
from pathlib import Path

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


def test_dispatch_persists_trajectories_db(tmp_path):
    os.chdir(tmp_path)
    task = TaskSchema(id="t1", title="teste", agent_id="cpo")
    dispatcher = TaskDispatcher(mock_llm=True)
    result = dispatcher.dispatch(task, project_id="proj")
    assert isinstance(result, dict)
    assert Path(".loopforge/trajectories.db").exists()
    assert "proj-t1" in dispatcher.list_checkpoints()


def test_resume_after_dispatch(tmp_path):
    os.chdir(tmp_path)
    task = TaskSchema(id="t2", title="teste", agent_id="cpo")
    dispatcher = TaskDispatcher(mock_llm=True)
    dispatcher.dispatch(task, project_id="proj")
    resumed = dispatcher.resume(project_id="proj", task_id="t2")
    assert isinstance(resumed, dict)
