"""
Validador de artefatos contra schemas do The Foundry.
Compila schemas JSON em Pydantic models dinâmicos.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, create_model


class ValidationResult:
    """Resultado da validação de um artefato."""

    def __init__(self, valid: bool, data: Any = None, errors: list[str] | None = None):
        self.valid = valid
        self.data = data
        self.errors = errors or []

    def __bool__(self) -> bool:
        return self.valid


class ArtifactValidator:
    """Carrega schemas JSON do Foundry e valida artefatos contra eles."""

    def __init__(self, schemas_dir: str | Path):
        self.schemas_dir = Path(schemas_dir)
        self._cache: dict[str, type[BaseModel]] = {}

    def _load_json(self, name: str) -> dict:
        # Garantir extensão .json para compatibilidade com arquivos do Foundry
        if not name.endswith(".json"):
            name = f"{name}.json"
        path = self.schemas_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Schema não encontrado: {path}")
        with open(path) as f:
            return json.load(f)

    def _compile_model(self, schema_id: str, schema: dict) -> type[BaseModel]:
        """Compila schema JSON em Pydantic model dinâmico."""
        if schema_id in self._cache:
            return self._cache[schema_id]

        fields: dict[str, Any] = {}
        required = set(schema.get("required", []))

        for prop_name, prop_schema in schema.get("properties", {}).items():
            field_type = self._resolve_type(prop_schema)
            if prop_name in required:
                fields[prop_name] = (field_type, ...)
            else:
                fields[prop_name] = (Optional[field_type], None)

        model = create_model(schema_id, **fields)
        self._cache[schema_id] = model
        return model

    def _resolve_type(self, prop: dict) -> type:
        """Resolve tipo JSON/Pydantic recursivamente."""
        ref = prop.get("$ref")
        if ref:
            return dict  # Simplificado: referências externas viram dict

        json_type = prop.get("type", "string")

        if json_type == "string":
            return str
        elif json_type in ("integer", "number"):
            return float
        elif json_type == "boolean":
            return bool
        elif json_type == "array":
            items = prop.get("items", {})
            item_type = self._resolve_type(items)
            return list[item_type]  # type: ignore
        elif json_type == "object":
            if "properties" in prop:
                return create_model(
                    f"Nested_{prop.get('title', 'Object')}",
                    **{
                        k: (self._resolve_type(v), ...)
                        for k, v in prop.get("properties", {}).items()
                    },
                )
            return dict
        return str

    def validate(self, schema_id: str, data: dict) -> ValidationResult:
        """Valida dict contra schema JSON compilado."""
        schema = self._load_json(schema_id)
        model = self._compile_model(schema_id, schema)

        try:
            validated = model.model_validate(data)
            return ValidationResult(valid=True, data=validated.model_dump())
        except Exception as e:
            return ValidationResult(valid=False, errors=[str(e)])

    def get_schema(self, schema_id: str) -> dict | None:
        """Retorna schema raw para inspeção."""
        try:
            return self._load_json(schema_id)
        except FileNotFoundError:
            return None


# Módulo de Ontologia
# from __future__ import annotations

# Importação condicional para evitar erros de importação
try:
    from typing import Optional
except ImportError:
    pass
