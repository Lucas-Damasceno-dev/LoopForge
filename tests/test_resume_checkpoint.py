"""Testes unitários e E2E para error recovery com checkpoint e o comando CLI 'lf resume'."""

import os

from click.testing import CliRunner

from lf.cli.commands.resume import resume_cmd
from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher


def test_dispatcher_checkpoint_save_and_resume(tmp_path):
    os.chdir(tmp_path)

    dispatcher = TaskDispatcher(mock_llm=True)
    task = TaskSchema(id="task-resume-1", title="Build authentication service", agent_id="cpo")

    # 1. Executa pipeline gravando checkpoint
    result = dispatcher.dispatch(task=task, project_id="proj-test")
    assert not result.get("error")

    # 2. Verifica se thread ID está na lista de checkpoints
    checkpoints = dispatcher.list_checkpoints()
    assert "proj-test-task-resume-1" in checkpoints

    # 3. Executa retomada via dispatcher.resume
    resumed_result = dispatcher.resume(project_id="proj-test", task_id="task-resume-1")
    assert resumed_result.get("next_agent") in ("devops", "__end__", "END", "FINISH", None)



def test_cli_resume_command_list_and_exec(tmp_path):
    os.chdir(tmp_path)
    runner = CliRunner()

    # Dispatch primeiro para criar um checkpoint
    dispatcher = TaskDispatcher(mock_llm=True)
    task = TaskSchema(id="task-cli-1", title="Build landing page", agent_id="cpo")
    dispatcher.dispatch(task=task, project_id="proj-cli")

    # Teste lf resume --list
    res_list = runner.invoke(resume_cmd, ["--list"])
    assert res_list.exit_code == 0
    assert "proj-cli-task-cli-1" in res_list.output

    # Teste lf resume --project-id proj-cli --task-id task-cli-1
    res_exec = runner.invoke(resume_cmd, ["--project-id", "proj-cli", "--task-id", "task-cli-1"])
    assert res_exec.exit_code == 0
    assert "Retomando pipeline" in res_exec.output or "concluída" in res_exec.output
