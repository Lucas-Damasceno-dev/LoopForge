"""P1-4: isolamento cross-run do workdir.

Antes do fix, todas as tasks de um mesmo projeto compartilhavam
`/tmp/loopforge/{project_id}` — artefatos de uma run Java (pom.xml, target/,
test_reports/) contaminavam a run Python seguinte. Este teste garante:
- output_dir único por task (sufixo sanitizado a partir do task.id);
- fallback para o diretório do projeto quando o id é vazio;
- `_cleanup_stale_project_dirs` remove artefatos de build/cache regeneráveis
  (target/, test_reports/, .pytest_cache/, src/) mas PRESERVA .venv/.
"""

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.nodes.developer import _cleanup_stale_project_dirs


def _make_dispatcher() -> TaskDispatcher:
    return TaskDispatcher(mock_llm=True, interactive=False)


def test_build_initial_state_output_dir_unico_por_task():
    """Task com id 'proj-x/task-run-abc' → diretório isolado sob o projeto (sem duplicar o prefixo)."""
    task = TaskSchema(id="proj-x/task-run-abc", title="Test Task")
    state = _make_dispatcher()._build_initial_state(task, project_id="proj-x")

    assert state["output_dir"] == "/tmp/loopforge/proj-x/task-run-abc"


def test_build_initial_state_output_dir_fallback_quando_id_vazio():
    """Id vazio → fallback para o diretório do projeto, sem sufixo extra."""
    task = TaskSchema(id="", title="Test Task")
    state = _make_dispatcher()._build_initial_state(task, project_id="proj-x")

    assert state["output_dir"] == "/tmp/loopforge/proj-x"


def test_cleanup_stale_dirs_remove_artefatos_e_preserva_venv(tmp_path):
    """target/, test_reports/, .pytest_cache/ e src/ são removidos; .venv/ é preservado."""
    for name in ("target", "test_reports", ".pytest_cache", "src", ".venv"):
        (tmp_path / name).mkdir()
    (tmp_path / "target" / "app.jar").write_text("x")
    (tmp_path / "test_reports" / "report.txt").write_text("x")
    (tmp_path / ".pytest_cache" / "cache.json").write_text("x")
    (tmp_path / "src" / "main.py").write_text("print(1)")
    (tmp_path / ".venv" / "bin").mkdir()
    (tmp_path / ".venv" / "bin" / "python").write_text("")

    _cleanup_stale_project_dirs([str(tmp_path)], stack="python")

    assert not (tmp_path / "target").exists()
    assert not (tmp_path / "test_reports").exists()
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "src").exists()
    assert (tmp_path / ".venv").exists()
