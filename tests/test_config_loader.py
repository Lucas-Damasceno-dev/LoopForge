import json

import pytest
from pydantic import ValidationError

from lf.config.loader import load_config


def test_load_config_json_valido_carrega_via_json(tmp_path: pytest.TempPathFactory) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"llm_provider": "openrouter", "llm_model": "oc/deepseek-v4-flash-free"}),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.llm_provider == "openrouter"
    assert config.llm_model == "oc/deepseek-v4-flash-free"


def test_load_config_json_invalido_mas_yaml_valido_lanca_jsondecodeerror(
    tmp_path: pytest.TempPathFactory,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("openrouter_api_key: abc", encoding="utf-8")

    with pytest.raises(json.JSONDecodeError):
        load_config(config_path)


def test_load_config_yaml_carrega_via_yaml(tmp_path: pytest.TempPathFactory) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("llm_provider: openrouter\nllm_model: oc/deepseek-v4-flash-free\n", encoding="utf-8")

    config = load_config(config_path)

    assert config.llm_provider == "openrouter"
    assert config.llm_model == "oc/deepseek-v4-flash-free"


def test_load_config_arquivo_vazio_retorna_default(tmp_path: pytest.TempPathFactory) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("", encoding="utf-8")

    config = load_config(config_path)

    assert config.model_dump() == load_config(tmp_path / "inexistente.json").model_dump()


def test_load_config_json_null_retorna_default(tmp_path: pytest.TempPathFactory) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("null", encoding="utf-8")

    config = load_config(config_path)

    assert config.llm_provider == "openrouter"
    assert config.model_dump() == load_config(tmp_path / "inexistente.json").model_dump()


def test_load_config_arquivo_inexistente_preserva_comportamento_atual(
    tmp_path: pytest.TempPathFactory,
) -> None:
    config = load_config(tmp_path / "nao-existe.json")

    assert config.model_dump() == load_config(tmp_path / "outro-nao-existe.json").model_dump()


def test_load_config_campo_desconhecido_lanca_validationerror(tmp_path: pytest.TempPathFactory) -> None:
    """Typos em .loopforge.json (ex.: 'budjet_limit_usd') falham alto (extra=forbid)."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"llm_provider": "openrouter", "budjet_limit_usd": 5.0}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="budjet_limit_usd"):
        load_config(config_path)


def test_load_config_stack_com_campo_desconhecido_lanca_validationerror(
    tmp_path: pytest.TempPathFactory,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"stack": {"language": "python", "framewrok": "fastapi"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="framewrok"):
        load_config(config_path)


def test_load_config_json_completo_valido_carrega(tmp_path: pytest.TempPathFactory) -> None:
    """Config válida (espelha .loopforge.json real) carrega sem erro com extra=forbid."""
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "project_id": "loopforge",
                "project_name": "LoopForge",
                "version": "6.0.0",
                "ontology_path": "examples/the-foundry",
                "stack": {
                    "language": "python",
                    "framework": "fastapi",
                    "testing_harness": "pytest",
                    "package_manager": "pip",
                },
                "llm_provider": "openrouter",
                "llm_model": "oc/deepseek-v4-flash-free",
                "budget_limit_usd": 10.0,
                "max_parallel_tasks": 2,
                "plan": {"tasks": [], "graph": {}},
            }
        ),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.project_id == "loopforge"
    assert config.llm_model == "oc/deepseek-v4-flash-free"
    assert config.stack.framework == "fastapi"
