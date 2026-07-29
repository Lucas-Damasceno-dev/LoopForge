from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TechStack(BaseModel):
    language: str = "python"
    framework: str = "fastapi"
    testing_harness: str = "pytest"
    package_manager: str = "pip"


def resolve_tech_stack(language: str, framework: str | None = None) -> TechStack:
    """Resolve coerente de stack, framework, test harness e package manager por linguagem."""
    lang = language.lower().strip()
    if lang == "java":
        fw = framework if framework and framework != "fastapi" else "spring-boot"
        return TechStack(language="java", framework=fw, testing_harness="junit", package_manager="maven")
    elif lang in ("javascript", "typescript", "js", "ts"):
        fw = framework if framework and framework != "fastapi" else "express"
        return TechStack(language="javascript", framework=fw, testing_harness="vitest", package_manager="npm")
    elif lang == "go":
        fw = framework if framework and framework != "fastapi" else "gin"
        return TechStack(language="go", framework=fw, testing_harness="gotest", package_manager="go")
    elif lang == "rust":
        fw = framework if framework and framework != "fastapi" else "actix"
        return TechStack(language="rust", framework=fw, testing_harness="cargotest", package_manager="cargo")
    else:
        fw = framework or "fastapi"
        return TechStack(language="python", framework=fw, testing_harness="pytest", package_manager="pip")


class ArtifactSchema(BaseModel):
    id: str
    schema_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    path: str = ""
    hash: str = ""


class TaskSchema(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    title: str
    status: Literal["pending", "running", "validating", "failed", "done"] = "pending"
    agent_id: str = "developer"
    persona: str = ""
    input_artifact_id: str = ""
    expected_schema: str = ""
    prompt: str = ""
    attempts: int = 0
    max_retries: int = 3
    depends_on: list[str] = Field(default_factory=list)
    stack: str | None = Field(None, description="Stack tecnológica opcional")
    routing_mode: str = "full"
    task_type: str = "feature"

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item, None)


class PlanSchema(BaseModel):
    model_config = ConfigDict(extra="ignore", from_attributes=True, validate_default=True)

    tasks: list[TaskSchema] = Field(default_factory=list)
    graph: dict[str, list[str]] = Field(default_factory=dict)

    @field_validator("tasks", mode="before")
    @classmethod
    def validate_tasks(cls, v: Any) -> Any:
        if isinstance(v, list):
            res = []
            for item in v:
                if isinstance(item, dict):
                    res.append(TaskSchema(**item))
                else:
                    res.append(item)
            return res
        return v


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
