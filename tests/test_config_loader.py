import json

import pytest

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


def test_load_config_arquivo_inexistente_preserva_comportamento_atual(
    tmp_path: pytest.TempPathFactory,
) -> None:
    config = load_config(tmp_path / "nao-existe.json")

    assert config.model_dump() == load_config(tmp_path / "outro-nao-existe.json").model_dump()
