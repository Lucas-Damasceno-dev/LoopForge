from lf.ontology.artifact_validator import ArtifactValidator


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
