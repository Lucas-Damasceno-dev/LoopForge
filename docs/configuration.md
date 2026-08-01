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
    llm_provider: str = "openrouter"        # "openrouter" | "google"
    llm_model: str = "oc/deepseek-v4-flash-free" # Modelo LLM (ex: auto/best-free)
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
  "llm_model": "oc/deepseek-v4-flash-free",
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
llm_model: oc/deepseek-v4-flash-free
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
| `OPENROUTER_MODEL` | `auto/best-free` | Modelo OpenRouter |
| `OPENROUTER_BASE_URL` | — | URL base customizada para OmniRoute |
| `OPENROUTER_TIMEOUT` | `120` | Segundos antes do timeout da chamada LLM HTTP; aumente p/ `300` com modelos de reasoning |
| `GEMINI_API_KEY` | — | API Key Google GenAI (fallback) |
| `OPENCODE_MODEL` | `auto/best-free` | Modelo para subprocesso OpenCode |
| `OPENCODE_MOCK` | `0` | `=1` ativa modo mock (sem subprocesso) |

### OmniRoute (proxy local)

OmniRoute expõe uma API compatível com OpenRouter em localhost. Configure as variáveis para apontar o LoopForge ao proxy local:

```bash
export OPENROUTER_BASE_URL=http://localhost:20128/v1
export OPENROUTER_API_KEY=sk-omniroute-local
export OPENROUTER_MODEL=oc/deepseek-v4-flash-free
export OPENCODE_MODEL=oc/deepseek-v4-flash-free
export OPENROUTER_TIMEOUT=300
```

> **Nota**: modelos de reasoning podem estourar o timeout default de `120s` em prompts grandes (o backoff em `src/lf/pipeline/llm_factory.py:64` eleva o timeout a cada tentativa, mas o valor base ainda é limitante). Use `OPENROUTER_TIMEOUT=300` para runs full, ou `OPENROUTER_MODEL=auto/best-fast` se preferir latência menor.

### `.env.example`

```env
# LoopForge v6 — Configuração de Ambiente

# Provedor primário (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
OPENROUTER_MODEL=auto/best-free
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# OPENROUTER_TIMEOUT=300

# Fallback Google GenAI
GEMINI_API_KEY=AIza-xxxxx

# Modelo para subprocesso OpenCode
OPENCODE_MODEL=auto/best-free

# Modo mock (sem chamadas LLM reais)
# OPENCODE_MOCK=1
```
