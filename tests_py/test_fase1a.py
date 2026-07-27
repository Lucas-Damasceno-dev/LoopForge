from lf.ontology.artifact_validator import ArtifactValidator
from lf.ontology.personas.registry import registry
from lf.ontology.schema_loader import OntologySchemaLoader


def test_schema_loader():
    loader = OntologySchemaLoader()
    schema = loader.load_json_schema("epic")
    assert isinstance(schema, dict)
    # Foundry schemas usam formato flat (field: type - description), não JSON Schema padrão
    assert "title" in schema
    assert "description" in schema


def test_artifact_validator():
    validator = ArtifactValidator(
        "examples/the-foundry/company_context/shared_knowledge/artifact_templates"
    )
    result = validator.validate("epic_schema.json", {
        "id": "E-001",
        "title": "Epic Title",
        "description": "Description",
        "business_objectives": ["Obj1"],
        "hypothesis": "Hypothesis",
        "scope_in": ["Feature"],
        "scope_out": ["Scope"],
        "success_metrics": ["Metric"],
        "stakeholders": {"owner": "CPO", "consulted": []},
        "dates": {"created_at": "2026-01-01", "started_at": "2026-01-01"},
    })
    assert result.valid, f"Validation failed: {result.errors}"


def test_persona_registry():
    cpo = registry.get_profile("cpo")
    assert cpo is not None
    assert cpo.role == "Chief Product Officer"
    assert "Define epics" in cpo.responsibilities

    unknown = registry.resolve("unknown_role")
    assert unknown.id == "unknown_role"
    assert unknown.mission == "Execute task as unknown_role"
