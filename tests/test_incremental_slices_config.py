"""Testes de configuração do incremental (milestone v7 5.1).

TaskSchema.incremental_slices default False; AdePipeline com defaults
(max_slices 8, slice_max_retries 3); ade.yaml pipeline.incremental_slices: true
ativa o modo no estado inicial do dispatcher; build_slices capa por max_slices.
"""

from lf.config.schema import AdeConfig, AdePipeline, TaskSchema
from lf.orchestrator.task_dispatcher import TaskDispatcher
from lf.pipeline.nodes.slices import build_slices


def test_taskschema_incremental_default_false():
    task = TaskSchema(id="cfg-1", title="t")
    assert task.incremental_slices is False


def test_taskschema_incremental_ligado_explicitamente():
    task = TaskSchema(id="cfg-2", title="t", incremental_slices=True)
    assert task.incremental_slices is True


def test_ade_pipeline_defaults():
    cfg = AdeConfig()
    assert isinstance(cfg.pipeline, AdePipeline)
    assert cfg.pipeline.incremental_slices is False
    assert cfg.pipeline.max_slices == 8
    assert cfg.pipeline.slice_max_retries == 3


def test_ade_yaml_ativa_pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_WORKDIR_BASE", str(tmp_path / "workbase"))
    (tmp_path / ".loopforge").mkdir()
    (tmp_path / ".loopforge" / "ade.yaml").write_text(
        "pipeline:\n  incremental_slices: true\n  max_slices: 4\n  slice_max_retries: 2\n",
        encoding="utf-8",
    )
    task = TaskSchema(id="cfg-3", title="t", stack="python")
    state = TaskDispatcher(mock_llm=True)._build_initial_state(task, "proj-cfg")
    assert state["incremental_slices"] is True
    assert state["slice_max_retries"] == 2


def test_ade_yaml_off_mantem_false(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LF_WORKDIR_BASE", str(tmp_path / "workbase"))
    task = TaskSchema(id="cfg-4", title="t", stack="python")
    state = TaskDispatcher(mock_llm=True)._build_initial_state(task, "proj-cfg")
    assert state["incremental_slices"] is False


def test_build_slices_cap_max_slices():
    stories = [{"id": f"US{i:03d}"} for i in range(12)]
    slices = build_slices(stories, max_slices=8)
    assert len(slices) == 8
    assert slices[0]["story"]["id"] == "US000"
    # Estrutura do slice
    first = slices[0]
    assert first["modules"] == []
    assert first["contract_tests"] == ""
    assert first["status"] == "pending"
    assert first["attempts"] == 0
    assert first["test_report"] == {}


def test_build_slices_contract_map():
    stories = [{"id": "US001"}, {"id": "US002"}]
    slices = build_slices(stories, contract_map={"US001": "tests de US001"})
    assert slices[0]["contract_tests"] == "tests de US001"
    assert slices[1]["contract_tests"] == ""
