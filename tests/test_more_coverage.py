import json
from unittest.mock import MagicMock, patch

import pytest

from lf.config.loader import load_config, save_config
from lf.config.schema import LoopForgeConfig
from lf.ontology.artifact_validator import ArtifactValidator
from lf.pipeline.llm_factory import call_openrouter_api


def test_artifact_validator(tmp_path):
    schema_data = {
        "title": "Epic",
        "type": "object",
        "required": ["id", "title"],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "count": {"type": "integer"},
            "active": {"type": "boolean"},
            "items": {"type": "array", "items": {"type": "string"}},
            "nested": {"type": "object", "properties": {"sub": {"type": "string"}}},
        },
    }
    schema_file = tmp_path / "epic_schema.json"
    schema_file.write_text(json.dumps(schema_data), encoding="utf-8")

    validator = ArtifactValidator(schemas_dir=tmp_path)
    assert validator.get_schema("epic_schema") is not None
    assert validator.get_schema("non_existent") is None

    # Valid data
    valid_data = {
        "id": "E-001",
        "title": "Valid Epic",
        "count": 5,
        "active": True,
        "items": ["a", "b"],
        "nested": {"sub": "value"},
    }
    val_res = validator.validate("epic_schema", valid_data)
    assert bool(val_res) is True
    assert val_res.valid is True

    # Invalid data (missing required field)
    invalid_data = {"title": "No ID Epic"}
    invalid_res = validator.validate("epic_schema", invalid_data)
    assert bool(invalid_res) is False
    assert len(invalid_res.errors) > 0

    # Non-existent schema
    with pytest.raises(FileNotFoundError):
        validator.validate("missing_schema", {})


def test_llm_factory_openrouter(tmp_path):
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter response text"}}]
        }
        mock_post.return_value = mock_response

        res_text, res_usage = call_openrouter_api(
            prompt="Hello OpenRouter",
            model="inclusionai/ling-3.0-flash:free",
            api_key="test-key",
        )
        assert res_text == "OpenRouter response text"
        assert res_usage is None

        # Test error response
        mock_response.status_code = 500
        mock_response.text = "Internal Error"
        with pytest.raises(RuntimeError):
            call_openrouter_api(prompt="Test", api_key="test-key")


def test_config_load_and_save(tmp_path):
    cfg_file = tmp_path / ".loopforge.json"
    cfg = LoopForgeConfig(project_id="test-project", project_name="Test Vision")
    save_config(cfg, config_path=cfg_file)

    loaded = load_config(config_path=cfg_file)
    assert loaded.project_id == "test-project"
    assert loaded.project_name == "Test Vision"

    yaml_file = tmp_path / ".loopforge.yaml"
    save_config(cfg, config_path=yaml_file)
    loaded_yaml = load_config(config_path=yaml_file)
    assert loaded_yaml.project_id == "test-project"
