# Configuração do LoopForge v6

O LoopForge é configurado via arquivo `.loopforge.json` ou `.loopforge.yml` na raiz do projeto. O schema é validado em runtime através dos modelos **Pydantic v2**.

---

## Schema Completo (Python / Pydantic v2)

```python
class LoopForgeConfig(BaseModel):
    project_id: str = "loopforge_project"
    project_name: str = "LoopForge Project"
    version: str = "6.0.0"
    ontology_path: str = "examples/the-foundry"
    stack: TechStack = Field(default_factory=TechStack)
    llm_provider: str = "google"
    llm_model: str = "gemini-2.0-flash"
    budget_limit_usd: float = 10.0
    max_parallel_tasks: int = 2
    plan: PlanSchema = Field(default_factory=PlanSchema)


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
    stack: str | None = Field(None, description="Stack tecnológica opcional (Tech Lead decide se omitido)")
    routing_mode: str = "full"
    task_type: str = "feature"
```

---

## Exemplo de `.loopforge.json`

```json
{
  "project_id": "meu-projeto",
  "project_name": "Meu Projeto Autônomo",
  "version": "6.0.0",
  "ontology_path": "examples/the-foundry",
  "budget_limit_usd": 10.0,
  "max_parallel_tasks": 2,
  "llm_provider": "openrouter",
  "llm_model": "inclusionai/ling-3.0-flash:free",
  "plan": {
    "tasks": [
      {
        "id": "T-001",
        "title": "API REST de tarefas com autenticação JWT em Java Spring Boot",
        "agent_id": "cpo",
        "routing_mode": "full",
        "status": "pending",
        "stack": null
      }
    ]
  }
}
```
