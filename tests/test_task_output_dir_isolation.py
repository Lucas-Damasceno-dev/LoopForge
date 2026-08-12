"""P1-4/AUD-2026-08: isolamento cross-run do workdir.

Antes do fix, runs CLI consecutivas (project_id ``loopforge_project`` + task.id
``task-1`` fixos) compartilhavam `/tmp/loopforge/loopforge_project/task-1` —
artefatos de uma run Java (pom.xml, target/, test_reports/) contaminavam a run
Python seguinte. Este teste garante:
- output_dir único por task (sufixo sanitizado a partir do task.id);
- output_dir único por EXECUÇÃO no fluxo CLI (run_key uuid por dispatch);
- base configurável via LF_WORKDIR_BASE;
- `_cleanup_stale_project_dirs` remove artefatos de build/cache regeneráveis
  (target/, test_reports/, .pytest_cache/, .venv/, node_modules/, __pycache__/)
  e manifestos estrangeiros (pom.xml em stack python), preservando o
  código-fonte quando artifacts_only=True.
"""

from lf.config.schema import TaskSchema
from lf.config.workdir import get_workdir_base
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


def test_dispatch_cli_workdir_unico_por_execucao(monkeypatch):
    """Fluxo CLI (project_id fixo + task.id fixo) → workdir único por dispatch.

    Antes: 2 runs consecutivas colidiam em `/tmp/loopforge/loopforge_project/task-1`.
    Agora cada dispatch gera um run_key `run-{uuid}` — diretórios distintos.
    """
    calls: list[dict] = []

    async def _fake_dispatch_async(self, initial_state, thread_id, task, project_id):
        calls.append(initial_state)
        return initial_state

    monkeypatch.setattr(TaskDispatcher, "_dispatch_async", _fake_dispatch_async)

    task = TaskSchema(id="task-1", title="CLI Task", agent_id="cpo", stack="python")
    dispatcher = _make_dispatcher()

    st1 = dispatcher.dispatch(task, project_id="loopforge_project")
    st2 = dispatcher.dispatch(task, project_id="loopforge_project")

    out1 = st1["output_dir"]
    out2 = st2["output_dir"]
    assert out1 != out2, f"2 dispatches CLI usaram o mesmo workdir: {out1}"
    base = get_workdir_base()
    assert out1.startswith(f"{base}/run-") and out2.startswith(f"{base}/run-")
    assert out1.endswith("/task-1") and out2.endswith("/task-1")


def test_workdir_base_configuravel_via_env(monkeypatch, tmp_path):
    """LF_WORKDIR_BASE redefine a base — sem quebrar o esquema de output_dir."""
    base = tmp_path / "runs"
    monkeypatch.setenv("LF_WORKDIR_BASE", str(base))

    assert get_workdir_base() == str(base)

    task = TaskSchema(id="task-1", title="Test Task")
    state = _make_dispatcher()._build_initial_state(task, project_id="proj-x")
    assert state["output_dir"] == f"{base}/proj-x/task-1"

    # Default preservado quando env ausente
    monkeypatch.delenv("LF_WORKDIR_BASE")
    assert get_workdir_base() == "/tmp/loopforge"


def test_cleanup_stale_dirs_remove_artefatos_e_venv(tmp_path):
    """target/, test_reports/, .pytest_cache/, src/, .venv/, node_modules/ e
    __pycache__/ são removidos; pom.xml estrangeiro (stack python) também."""
    for name in ("target", "test_reports", ".pytest_cache", "src", ".venv", "node_modules", "__pycache__"):
        (tmp_path / name).mkdir()
    (tmp_path / "target" / "app.jar").write_text("x")
    (tmp_path / "test_reports" / "report.txt").write_text("x")
    (tmp_path / ".pytest_cache" / "cache.json").write_text("x")
    (tmp_path / "src" / "main.py").write_text("print(1)")
    (tmp_path / ".venv" / "bin").mkdir()
    (tmp_path / ".venv" / "bin" / "python").write_text("")
    (tmp_path / "node_modules" / "dep.js").write_text("x")
    (tmp_path / "__pycache__" / "mod.pyc").write_text("x")
    (tmp_path / "pom.xml").write_text("<project/>")

    _cleanup_stale_project_dirs([str(tmp_path)], stack="python")

    assert not (tmp_path / "target").exists()
    assert not (tmp_path / "test_reports").exists()
    assert not (tmp_path / ".pytest_cache").exists()
    assert not (tmp_path / "src").exists()
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / "node_modules").exists()
    assert not (tmp_path / "__pycache__").exists()
    # pom.xml é manifesto ESTRANGEIRO à stack python → removido
    assert not (tmp_path / "pom.xml").exists()


def test_cleanup_artifacts_only_preserva_source(tmp_path):
    """artifacts_only=True (fim de run): artefatos regeneráveis e manifestos
    estrangeiros saem, mas o código-fonte da run (src/, generated_code.py) fica."""
    for name in ("target", "test_reports", ".venv", "node_modules", "__pycache__", "src"):
        (tmp_path / name).mkdir()
    (tmp_path / "target" / "app.jar").write_text("x")
    (tmp_path / "src" / "main.py").write_text("print(1)")
    (tmp_path / "generated_code.py").write_text("def main():\n    pass")
    (tmp_path / "pom.xml").write_text("<project/>")

    _cleanup_stale_project_dirs([str(tmp_path)], stack="python", artifacts_only=True)

    assert not (tmp_path / "target").exists()
    assert not (tmp_path / "test_reports").exists()
    assert not (tmp_path / ".venv").exists()
    assert not (tmp_path / "node_modules").exists()
    assert not (tmp_path / "__pycache__").exists()
    assert not (tmp_path / "pom.xml").exists()
    # Código-fonte preservado (PR/diff dependem dele)
    assert (tmp_path / "src" / "main.py").exists()
    assert (tmp_path / "generated_code.py").exists()
