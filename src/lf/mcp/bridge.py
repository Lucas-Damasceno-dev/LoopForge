"""Conversão de schemas MCP (JSON Schema) em Pydantic Tool Definitions."""
from typing import Any

from pydantic import BaseModel, create_model


def json_schema_to_pydantic(name: str, schema: dict[str, Any]) -> type[BaseModel]:
    fields: dict[str, Any] = {}
    for prop, meta in (schema.get("properties") or {}).items():
        ptype = meta.get("type", "string")
        py_type = {"string": str, "integer": int, "number": float, "boolean": bool}.get(ptype, str)
        required = prop in (schema.get("required") or [])
        fields[prop] = (py_type if required else py_type | None, ... if required else None)
    return create_model(name, **fields)


def tools_to_langgraph(tools: list[dict]) -> list[dict]:
    """Retorna [{name, description, pydantic_model}] pronto para BaseTool da Fase 2."""
    out = []
    for t in tools:
        model = json_schema_to_pydantic(t["name"], t.get("inputSchema") or {})
        out.append({"name": t["name"], "description": t.get("description", ""), "pydantic_model": model})
    return out
