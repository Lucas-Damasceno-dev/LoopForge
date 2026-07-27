from typing import Any, Literal
from pydantic import BaseModel, Field


class TechStack(BaseModel):
    language: str = "python"
    framework: str = "fastapi"
    testing_harness: str = "pytest"
    package_manager: str = "pip"


class ArtifactSchema(BaseModel):
    id: str
    schema_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    path: str = ""
    hash: str = ""


class TaskSchema(BaseModel):
    id: str
    title: str
    status: Literal["pending", "running", "validating", "failed", "done"] = "pending"
    agent_id: str = "developer"
    input_artifact_id: str = ""
    expected_schema: str = ""
    prompt: str = ""
    attempts: int = 0
    max_retries: int = 3
    depends_on: list[str] = Field(default_factory=list)


class PlanSchema(BaseModel):
    tasks: list[TaskSchema] = Field(default_factory=list)
    graph: dict[str, list[str]] = Field(default_factory=dict)


class LoopForgeConfig(BaseModel):
    project_id: str = "loopforge_project"
    project_name: str = "LoopForge Project"
    version: str = "6.0.0"
    ontology_path: str = "examples/the-foundry"
    stack: TechStack = Field(default_factory=TechStack)
    llm_provider: str = "google"
    llm_model: str = "gemini-1.5-flash"
    budget_limit_usd: float = 10.0
    max_parallel_tasks: int = 2
    plan: PlanSchema = Field(default_factory=PlanSchema)
