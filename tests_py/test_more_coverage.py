import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from lf.ontology.artifact_validator import ArtifactValidator, ValidationResult
from lf.ontology.schema_loader import OntologySchemaLoader
from lf.pipeline.llm_factory import get_llm, call_openrouter_api
from lf.config.loader import load_config, save_config
from lf.config.schema import LoopForgeConfig



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


def test_ontology_schema_loader(tmp_path):
    loader = OntologySchemaLoader(ontology_root=tmp_path)

    # Test fallback schema when not found
    schema = loader.load_json_schema("epic")
    assert schema["type"] == "object"

    # Test fallback persona when not found
    persona = loader.load_persona("developer")
    assert "Persona for developer" in persona

    # Test existing schema & persona
    templates_dir = tmp_path / "company_context" / "shared_knowledge" / "artifact_templates"
    templates_dir.mkdir(parents=True)
    (templates_dir / "epic_schema.json").write_text('{"title": "Custom Epic"}', encoding="utf-8")

    persona_dir = tmp_path / "company_context" / "cpo"
    persona_dir.mkdir(parents=True)
    (persona_dir / "cpo.md").write_text("# CPO Persona Prompt", encoding="utf-8")

    assert loader.load_json_schema("epic")["title"] == "Custom Epic"
    assert loader.load_persona("cpo") == "# CPO Persona Prompt"


def test_llm_factory_openrouter(tmp_path):
    with patch("httpx.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "OpenRouter response text"}}]
        }
        mock_post.return_value = mock_response

        res = call_openrouter_api(
            prompt="Hello OpenRouter",
            model="inclusionai/ling-3.0-flash:free",
            api_key="test-key",
        )
        assert res == "OpenRouter response text"

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

    # Test yaml support
    yaml_file = tmp_path / ".loopforge.yaml"
    save_config(cfg, config_path=yaml_file)
    loaded_yaml = load_config(config_path=yaml_file)
    assert loaded_yaml.project_id == "test-project"


