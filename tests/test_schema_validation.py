import pytest
from pydantic import ValidationError

from lf.config.schema import LoopForgeConfig, TaskSchema


@pytest.mark.parametrize("field,value", [("routing_mode", "invalid"), ("task_type", "invalid"), ("complexity_level", "invalid")])
def test_task_schema_rejeita_literais_invalidos(field: str, value: str):
    payload = {"id": "task-1", "title": "Teste", field: value}
    with pytest.raises(ValidationError):
        TaskSchema(**payload)


def test_loopforge_config_rejeita_budget_negativo():
    with pytest.raises(ValidationError):
        LoopForgeConfig(budget_limit_usd=-0.01)


@pytest.mark.parametrize("value", [0, -1])
def test_loopforge_config_rejeita_max_parallel_tasks_invalido(value: int):
    with pytest.raises(ValidationError):
        LoopForgeConfig(max_parallel_tasks=value)


def test_task_schema_aceita_valores_validos():
    task = TaskSchema(
        id="task-1",
        title="Teste",
        routing_mode="explore",
        task_type="bugfix",
        complexity_level="advanced",
    )
    assert task.routing_mode == "explore"
    assert task.task_type == "bugfix"
    assert task.complexity_level == "advanced"


def test_defaults_preservados():
    task = TaskSchema(id="task-1", title="Teste")
    config = LoopForgeConfig()
    assert task.routing_mode == "full"
    assert task.task_type == "feature"
    assert task.complexity_level == "standard"
    assert config.budget_limit_usd == 10.0
    assert config.max_parallel_tasks == 2
