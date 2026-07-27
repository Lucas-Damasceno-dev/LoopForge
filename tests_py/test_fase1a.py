from lf.ontology.artifact_validator import validate_artifact_data
from lf.ontology.personas.registry import registry
from lf.ontology.schema_loader import OntologySchemaLoader


def test_schema_loader():
    loader = OntologySchemaLoader()
    schema = loader.load_json_schema("epic")
    assert isinstance(schema, dict)


def test_artifact_validator():
    valid, msg = validate_artifact_data({"id": "epic-1", "title": "Epic Title"}, "epic")
    assert valid
    assert msg == ""

    invalid, msg_inv = validate_artifact_data({"title": "No ID"}, "user_story")
    assert not invalid
    assert "Missing required fields" in msg_inv


def test_persona_registry():
    cpo = registry.resolve("cpo")
    assert cpo.role == "Chief Product Officer"
    assert "Define epics" in cpo.responsibilities
