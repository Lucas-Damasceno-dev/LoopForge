from typing import Any
from pydantic import BaseModel, ValidationError


def validate_artifact_data(data: dict[str, Any], schema_id: str) -> tuple[bool, str]:
    """
    Validates a dict artifact against basic required fields according to schema_id.
    Returns (is_valid, error_message).
    """
    if not isinstance(data, dict):
        return False, "Artifact data must be a dictionary"

    if schema_id == "epic":
        required = ["id", "title"]
    elif schema_id == "user_story":
        required = ["id", "title", "acceptance_criteria"]
    elif schema_id == "tech_spec":
        required = ["title"]
    elif schema_id == "test_execution_report":
        required = ["total_tests", "passed"]
    else:
        required = ["id"] if "id" in data else []

    missing = [req for req in required if req not in data]
    if missing:
        return False, f"Missing required fields for {schema_id}: {', '.join(missing)}"

    return True, ""
