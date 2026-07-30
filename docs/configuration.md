# Configuração do LoopForge v6

O LoopForge é configurado via arquivo `.loopforge.json` ou `.loopforge.yml` na raiz do projeto. O schema é validado em runtime através dos modelos **Pydantic v2** em `src/lf/config/schema.py`. O carregamento é feito por `load_config()` em `src/lf/config/loader.py` (suporta JSON e YAML).

---

## Schema do `TaskSchema`

```python
class TaskSchema(BaseModel):
    id: str
    title: str
    status: Literal["pending", "running", "validating", "failed", "done"] = "pending"
    agent_id: str = "developer"      # Nó de entrada (fallback se persona não definida)
    persona: str = ""                 # Persona do ontology (substitui agent_id quando definida)
    input_artifact_id: str = ""
    expected_schema: str = ""
    prompt: str = ""
    attempts: int = 0
    max_retries: int = 3
    depends_on: list[str] = Field(default_factory=list)
    stack: str | None = Field(None, description="Stack tecnológica opcional (Tech Lead decide se omitido)")
    routing_mode: str = "full"        # "full", "fast", "review-only", "explore"
    task_type: str = "feature"        # "feature", "bugfix", "refactor", "simple", "review"
```

A propriedade `persona` faz fallback para `agent_id` via `__getitem__()`.

---

## Schema do `LoopForgeConfig`

```python
class LoopForgeConfig(BaseModel):
    project_id: str = "loopforge_project"
    project_name: str = "LoopForge Project"
    version: str = "6.0.0"
    ontology_path: str = "examples/the-foundry"  # Caminho para ontologia The Foundry
    stack: TechStack = Field(default_factory=TechStack)  # TechStack(language, framework, testing_harness, package_manager)
    llm_provider: str = "google"        # "openrouter" | "google"
    llm_model: str = "gemini-1.5-flash" # Modelo LLM (ex: inclusionai/ling-3.0-flash:free)
    budget_limit_usd: float = 10.0      # Limite de gasto USD (usado pelo CircuitBreaker)
    max_parallel_tasks: int = 2
    plan: PlanSchema = Field(default_factory=PlanSchema)  # PlanSchema(tasks[], graph{})
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
        "persona": "cpo",
        "routing_mode": "full",
        "task_type": "feature",
        "status": "pending",
        "stack": null,
        "max_retries": 3
      }
    ]
  }
}
```

---

## Exemplo de `.loopforge.yml`

```yaml
project_id: meu-projeto
project_name: "Meu Projeto Autônomo"
version: "6.0.0"
ontology_path: examples/the-foundry
budget_limit_usd: 10.0
max_parallel_tasks: 2
llm_provider: openrouter
llm_model: inclusionai/ling-3.0-flash:free
plan:
  tasks:
    - id: T-001
      title: "CLI em Rust para processar CSV"
      persona: cpo
      routing_mode: full
      task_type: feature
      status: pending
      max_retries: 3
```

---

## Variáveis de Ambiente

| Variável | Default | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY` | — | API Key do OpenRouter (provedor primário) |
| `OPENROUTER_MODEL` | `inclusionai/ling-3.0-flash:free` | Modelo OpenRouter |
| `OPENROUTER_BASE_URL` | — | URL base customizada para OmniRoute |
| `GEMINI_API_KEY` | — | API Key Google GenAI (fallback) |
| `OPENCODE_MODEL` | `openrouter/inclusionai/ling-3.0-flash:free` | Modelo para subprocesso OpenCode |
| `OPENCODE_MOCK` | `0` | `=1` ativa modo mock (sem subprocesso) |

### `.env.example`

```env
# LoopForge v6 — Configuração de Ambiente

# Provedor primário (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
OPENROUTER_MODEL=inclusionai/ling-3.0-flash:free
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Fallback Google GenAI
GEMINI_API_KEY=AIza-xxxxx

# Modo mock (sem chamadas LLM reais)
# OPENCODE_MOCK=1
```
