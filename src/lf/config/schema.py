from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TechStack(BaseModel):
    language: str = "python"
    framework: str = "fastapi"
    testing_harness: str = "pytest"
    package_manager: str = "pip"


def resolve_tech_stack(language: str, framework: str | None = None) -> TechStack:
    """Resolve de stack utilizando o TechStackRegistry extensível."""
    from .registry import TechStackRegistry

    handler = TechStackRegistry.get(language)
    if handler:
        fw = framework if framework and framework != "fastapi" else handler.default_framework
        return TechStack(
            language=handler.language,
            framework=fw,
            testing_harness=handler.default_test_harness,
            package_manager=handler.default_package_manager,
        )

    # Fallback padronizado Python
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
    routing_mode: Literal["full", "fast", "patch", "review-only", "explore"] = "full"
    task_type: Literal["feature", "bugfix", "patch", "review", "explore", "fast", "simple"] = "feature"
    complexity_level: Literal["mvp", "standard", "advanced"] = "standard"

    def __getitem__(self, item: str) -> Any:
        if item == "persona":
            return getattr(self, "persona", "") or getattr(self, "agent_id", "")
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
    llm_provider: str = "openrouter"
    llm_model: str = "oc/deepseek-v4-flash-free"
    budget_limit_usd: float = Field(10.0, ge=0)
    max_parallel_tasks: int = Field(2, gt=0)
    plan: PlanSchema = Field(default_factory=PlanSchema)


class AdeMcpServer(BaseModel):
    name: str
    command: str
    args: list[str] = []
    tools_allowlist: list[str] = []
    enabled: bool = True


class AdeBudget(BaseModel):
    """Fonte única do budget (M-08): alimenta o CircuitBreaker do dispatcher."""
    max_usd: float = Field(10.0, ge=0, description="Limite de custo em USD por run (fonte única via ade.yaml)")


class AdeProviders(BaseModel):
    primary: str = "native"
    ollama_base_url: str = "http://localhost:11434"


class AdeHITL(BaseModel):
    timeout_seconds: int = 300


class AdeConfig(BaseModel):
    budget: AdeBudget = Field(default_factory=AdeBudget)
    mcp_servers: list[AdeMcpServer] = Field(default_factory=list)
    providers: AdeProviders = Field(default_factory=AdeProviders)
    hitl: AdeHITL = Field(default_factory=AdeHITL)
