import json
from pathlib import Path
from typing import Any


class OntologySchemaLoader:
    def __init__(self, ontology_root: str | Path = "examples/the-foundry"):
        self.root = Path(ontology_root)

    def load_json_schema(self, schema_name: str) -> dict[str, Any]:
        """Load JSON schema from company_context/shared_knowledge/artifact_templates/"""
        possible_paths = [
            self.root / "company_context" / "shared_knowledge" / "artifact_templates" / f"{schema_name}_schema.json",
            self.root / "company_context" / "shared_knowledge" / "artifact_templates" / f"{schema_name}.json",
            self.root / f"{schema_name}_schema.json",
        ]
        for path in possible_paths:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))

        # Fallback default schema
        return {
            "type": "object",
            "title": schema_name,
            "properties": {},
        }

    def load_persona(self, role: str) -> str:
        """Load markdown persona prompt file for given role"""
        role_lower = role.lower()
        possible_paths = [
            self.root / "company_context" / role_lower / f"{role_lower}.md",
            self.root / "company_context" / f"{role_lower}.md",
            self.root / f"{role_lower}.md",
        ]
        for path in possible_paths:
            if path.exists():
                return path.read_text(encoding="utf-8")
        return f"Persona for {role}"
