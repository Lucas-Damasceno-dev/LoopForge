"""AUD-2026-08: integração — 2 runs consecutivas de stacks diferentes (java → python).

Reproduz o bug P1-4: com project_id ``loopforge_project`` + task.id ``task-1``
fixos (fluxo CLI), runs consecutivas colidiam no MESMO workdir
`/tmp/loopforge/loopforge_project/task-1` e o pom.xml/target/ do run Java
contaminava o run Python seguinte. Agora:
- cada dispatch gera workdir único (run_key uuid por execução);
- ao final da run o dispatcher remove artefatos regeneráveis do workdir
  (`_cleanup_task_workdir`, só dentro de LF_WORKDIR_BASE).

Roda em modo MOCK (sem LLM/harness real). Base apontada para tmp_path.
"""

from pathlib import Path

from lf.config.schema import TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher

ARTIFACT_DIRS = ("target", "test_reports", ".venv", "node_modules", "__pycache__")


def _make_dispatcher() -> TaskDispatcher:
    return TaskDispatcher(mock_llm=True, interactive=False)


def _run_dispatch(dispatcher: TaskDispatcher, stack: str, project_id: str = "loopforge_project") -> dict:
    task = TaskSchema(id="task-1", title=f"Run {stack}", agent_id="cpo", stack=stack)
    result = dispatcher.dispatch(task, project_id=project_id)
    assert not result.get("error"), result.get("error")
    return result


def test_java_entao_python_sem_residuo(tmp_path, monkeypatch):
    """Java → Python (mock): workdirs distintos e sem resíduo no segundo."""
    base = tmp_path / "loopforge"
    monkeypatch.setenv("LF_WORKDIR_BASE", str(base))

    dispatcher = _make_dispatcher()

    run_java = _run_dispatch(dispatcher, stack="java")
    run_python = _run_dispatch(dispatcher, stack="python")

    out_java = Path(run_java["output_dir"])
    out_python = Path(run_python["output_dir"])

    # Workdirs ÚNICOS por execução (antes: colidiam em .../loopforge_project/task-1)
    assert out_java != out_python, f"runs java/python usaram o mesmo workdir: {out_java}"
    assert str(out_java).startswith(f"{base}/run-")
    assert str(out_python).startswith(f"{base}/run-")

    # Run 1 (java): manifesto próprio preservado (Maven do run atual precisa dele)
    assert (out_java / "pom.xml").exists(), "pom.xml do run java deveria existir"
    assert (out_java / "src" / "main" / "java" / "Main.java").exists()

    # Run 2 (python): SEM resíduo do run java — nada de pom.xml nem artefatos
    assert (out_python / "pyproject.toml").exists(), "run python deveria gerar pyproject.toml"
    assert not (out_python / "pom.xml").exists(), f"resíduo java no run python: {out_python / 'pom.xml'}"
    for name in ARTIFACT_DIRS:
        assert not (out_python / name).exists(), f"resíduo de artefato no run python: {out_python / name}"

    # Fim de run: artefatos regeneráveis do run java também limpos
    for name in ARTIFACT_DIRS:
        assert not (out_java / name).exists(), f"artefato não limpo ao final: {out_java / name}"


def test_cleanup_task_workdir_remove_artefatos_e_preserva_fonte(tmp_path, monkeypatch):
    """`_cleanup_task_workdir` remove artefatos + pom.xml estrangeiro, preserva fonte."""
    base = tmp_path / "base"
    monkeypatch.setenv("LF_WORKDIR_BASE", str(base))

    workdir = base / "run-abc123" / "task-1"
    for name in ARTIFACT_DIRS:
        (workdir / name).mkdir(parents=True)
    (workdir / "target" / "app.jar").write_text("x")
    (workdir / "pom.xml").write_text("<project/>")
    (workdir / "generated_code.py").write_text("print(1)")
    (workdir / "tests").mkdir()
    (workdir / "tests" / "test_main.py").write_text("def test_ok():\n    assert True")

    _make_dispatcher()._cleanup_task_workdir({"output_dir": str(workdir), "stack": "python"})

    for name in ARTIFACT_DIRS:
        assert not (workdir / name).exists(), f"artefato deveria ser removido: {name}"
    assert not (workdir / "pom.xml").exists(), "pom.xml é estrangeiro em stack python"
    # Código-fonte gerado preservado (PR/diff dependem dele)
    assert (workdir / "generated_code.py").exists()
    assert (workdir / "tests" / "test_main.py").exists()


def test_cleanup_task_workdir_fora_da_base_ignorado(tmp_path, monkeypatch):
    """Path fora de LF_WORKDIR_BASE nunca é tocado (rm -rf arbitrário proibido)."""
    base = tmp_path / "base"
    monkeypatch.setenv("LF_WORKDIR_BASE", str(base))

    outside = tmp_path / "outside" / "run-x"
    (outside / "target").mkdir(parents=True)
    (outside / "target" / "app.jar").write_text("x")

    _make_dispatcher()._cleanup_task_workdir({"output_dir": str(outside), "stack": "python"})

    assert (outside / "target" / "app.jar").exists(), "workdir fora da base não deve ser limpo"


def test_workdir_unico_tambem_com_id_vazio(tmp_path, monkeypatch):
    """Até com task.id vazio (fallback pro diretório do projeto), 2 runs não colidem."""
    base = tmp_path / "loopforge"
    monkeypatch.setenv("LF_WORKDIR_BASE", str(base))

    dispatcher = _make_dispatcher()

    out_dirs = set()
    for stack in ("java", "python"):
        task = TaskSchema(id="", title=f"Run {stack}", agent_id="cpo", stack=stack)
        result = dispatcher.dispatch(task, project_id="loopforge_project")
        assert not result.get("error"), result.get("error")
        out_dirs.add(result["output_dir"])

    assert len(out_dirs) == 2, f"workdirs colidiram com id vazio: {out_dirs}"
