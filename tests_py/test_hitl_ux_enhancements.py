"""Testes unitários e de integração para todas as 12 melhorias de HITL e UX."""

import os
from unittest.mock import patch
import pytest
from click.testing import CliRunner
from httpx import ASGITransport, AsyncClient

from lf.api.app import create_app
from lf.api.database import close_db, init_db
from lf.cli.commands.diff import diff_cmd
from lf.cli.commands.explore import explore_cmd
from lf.cli.commands.run import run_cmd
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher, _send_notification


import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_test_env(tmp_path):
    os.chdir(tmp_path)
    os.environ["LF_API_TEST"] = "1"
    os.environ["LF_API_REQUIRE_AUTH"] = "false"
    await init_db()
    yield
    await close_db()
    os.environ.pop("LF_API_TEST", None)
    os.environ.pop("LF_API_REQUIRE_AUTH", None)


@pytest.mark.asyncio
async def test_api_human_decision_endpoints():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        # 1. Cria run
        run_resp = await client.post("/api/runs", json={"idea": "Test HITL run"})
        assert run_resp.status_code == 201
        run_id = run_resp.json()["id"]

        import asyncio
        await asyncio.sleep(0.2)

        # 2. Registra decisão humana
        dec_resp = await client.post(
            f"/api/runs/{run_id}/decide",
            json={
                "gate_node": "developer",
                "action": "adjust_prompt",
                "feedback_category": "bug",
                "feedback_message": "Fix null pointer",
                "user": "tester",
            },
        )
        assert dec_resp.status_code == 201
        assert dec_resp.json()["feedback_category"] == "bug"

        # 3. Lista decisões
        list_resp = await client.get(f"/api/runs/{run_id}/decisions")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 1


def test_task_dispatcher_hitl_visual_and_record_decision(tmp_path):
    dispatcher = TaskDispatcher(mock_llm=True, interactive=True, hitl_timeout_seconds=1)
    task = TaskSchema(id="task-ux-1", title="Build user dashboard", agent_id="cpo")

    # Patch input com timeout para simular aprovação automática 'c'
    with patch.object(dispatcher, "_get_input_with_timeout", return_value="c"):
        res = dispatcher.dispatch(task=task, project_id="proj-ux")
        assert not res.get("error")


def test_task_dispatcher_review_mode(tmp_path):
    dispatcher = TaskDispatcher(mock_llm=True, review_mode=True)
    task = TaskSchema(id="task-rev-1", title="Build microservice", agent_id="cpo")

    # Simula aprovação no modo revisão
    with patch.object(dispatcher, "_get_input_with_timeout", return_value="s"):
        res = dispatcher.dispatch(task=task, project_id="proj-rev")
        assert not res.get("error")


def test_send_notification():
    with patch("shutil.which", return_value="/usr/bin/notify-send"):
        with patch("subprocess.run") as mock_sub:
            _send_notification("Title", "Message")
            assert mock_sub.called


def test_cli_diff_command(tmp_path):
    runner = CliRunner()
    res = runner.invoke(diff_cmd, ["--project-id", "nonexistent"])
    assert res.exit_code == 0
    assert "Analisando alterações" in res.output


def test_cli_explore_command(tmp_path):
    os.makedirs(".loopforge", exist_ok=True)
    db_file = os.path.join(".loopforge", "telemetry.sqlite")
    open(db_file, "w").close()

    runner = CliRunner()
    res = runner.invoke(explore_cmd, ["--db-path", db_file])
    assert res.exit_code == 0
    assert "Explorer" in res.output



def test_cli_run_flags(tmp_path):
    runner = CliRunner()
    res = runner.invoke(run_cmd, ["--idea", "Test run flags", "--mock", "--review-mode", "--notify"])
    assert res.exit_code == 0
    assert "LoopForge Run" in res.output
