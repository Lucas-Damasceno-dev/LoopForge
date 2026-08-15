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
    routing_mode: str = "full"        # "full", "fast", "patch", "review-only", "explore"
    task_type: str = "feature"        # "feature", "bugfix", "patch", "review", "explore", "fast", "simple"
    complexity_level: str = "standard" # "mvp", "standard", "advanced"
    incremental_slices: bool = False  # Entrega incremental por user story (v7 5.1)
    model: str | None = None          # Override de modelo LLM por task
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
    llm_provider: str = "openrouter"        # nome do provedor (ex: openrouter, ollama)
    llm_model: str = "oc/deepseek-v4-flash-free" # Modelo LLM default
    budget_limit_usd: float = 10.0      # Limite legado; o CircuitBreaker usa budget.max_usd do .loopforge/ade.yaml
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
| `OPENROUTER_MODEL` | `oc/deepseek-v4-flash-free` | Modelo OpenRouter (1º na cadeia de resolução) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | URL base da API OpenRouter (ou OmniRoute local) |
| `OPENROUTER_TIMEOUT` | `300` | Segundos antes do timeout da chamada LLM HTTP (`600` para modelos de reasoning) |
| `OPENCODE_MODEL` | `oc/deepseek-v4-flash-free` | Modelo para subprocesso OpenCode (2º na cadeia de resolução) |
| `OPENCODE_MOCK` | `0` | `=1` ativa modo mock (sem subprocesso) |
| `LF_API_HOST` | `0.0.0.0` | Host do servidor FastAPI (`lf serve`) |
| `LF_API_PORT` | `8000` | Porta do servidor FastAPI |
| `LF_API_KEY` | — | API key exigida pela API (X-API-Key / HTTP Basic) |
| `LF_QUEUE_BACKEND` | `memory` | Fila de execução: `memory` (single-process, BC) ou `redis` (multi-worker) |
| `LF_REDIS_URL` | `redis://localhost:6379` | URL do Redis quando `LF_QUEUE_BACKEND=redis` |

### Operação multi-worker

Para escalar horizontalmente com `--workers > 1`, a fila, os eventos WebSocket e o rate limit precisam ser globais — isso exige Redis:

```bash
export LF_QUEUE_BACKEND=redis
export LF_REDIS_URL=redis://localhost:6379
lf serve --workers 2 --port 8000
```

- `lf serve --workers N` valida: `workers > 1` exige `LF_QUEUE_BACKEND=redis`; `--reload` é incompatível com `--workers > 1`.
- Com `docker compose up -d`, o serviço `redis` (imagem `redis:7-alpine`, volume `redis_data`) sobe junto e o app aponta para `redis://redis:6379` por padrão.
- Cada worker promove runs da fila global (máx. `runner.max_concurrent_runs` ativas no total), renova leases via heartbeat e entrega eventos WS apenas aos clientes conectados nele próprio (broadcast cross-worker via canal `lf:events`). Cancelamento de run é propagado entre workers via canal `lf:cancel`.

### OmniRoute (proxy local)

OmniRoute expõe uma API compatível com OpenRouter em localhost. Configure as variáveis para apontar o LoopForge ao proxy local:

```bash
export OPENROUTER_BASE_URL=http://localhost:20128/v1
export OPENROUTER_API_KEY=sk-omniroute-local
export OPENROUTER_MODEL=oc/deepseek-v4-flash-free
export OPENCODE_MODEL=oc/deepseek-v4-flash-free
export OPENROUTER_TIMEOUT=300
```

> **Nota**: modelos de reasoning podem estourar o timeout default de `300s` em prompts grandes (o backoff em `src/lf/pipeline/llm_factory.py:161` eleva o timeout a cada tentativa, mas o valor base ainda é limitante). Use `OPENROUTER_TIMEOUT=600` para runs full, ou um modelo de latência menor se preferir velocidade.

### `.env.example`

```env
# LoopForge v6 — Configuração de Ambiente

# Provedor primário (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
OPENROUTER_MODEL=deepseek-v4-flash-free
# OPENROUTER_BASE_URL=https://opencode.ai/zen/v1
# OPENROUTER_TIMEOUT=

# Modelo para subprocesso OpenCode
OPENCODE_MODEL=opencode/deepseek-v4-flash-free
# OPENCODE_TIMEOUT=

# Timeouts de auditoria e testes
# LF_AUDIT_TIMEOUT=
# LF_TEST_TIMEOUT=

# Modo mock (sem chamadas LLM reais)
# OPENCODE_MOCK=1

# Servidor FastAPI
LF_API_HOST=0.0.0.0
LF_API_PORT=8000
LF_API_KEY=

# Multi-worker (fila global)
# LF_QUEUE_BACKEND=memory   # memory (single-process, BC) | redis (multi-worker)
# LF_REDIS_URL=redis://localhost:6379
```

---

## `.loopforge/ade.yaml` (AdeConfig)

Configuração avançada de runtime em `.loopforge/ade.yaml` (carregada por `load_ade_config()` em `src/lf/config/loader.py`). Arquivo ausente → `AdeConfig()` com defaults. Campos principais:

```yaml
budget:
  max_usd: 10.0            # Fonte ÚNICA do CircuitBreaker (via load_budget_usd)
hitl:
  timeout_seconds: 300     # Timeout do gate HITL
  on_timeout: continue     # continue | abort | pause
runner:
  subprocess_timeout_seconds: 300  # 0 = sem timeout
  max_concurrent_runs: 2   # Fila E3: excedente nasce `queued`
  sandbox_enabled: false   # git worktree isolada em .slim/worktrees/
pipeline:
  incremental_slices: false
  max_slices: 8
  slice_max_retries: 3
memory:
  cross_project: false     # busca de lessons entre projetos
api_keys:
  roles: admin             # admin | runner | viewer (RBAC na API)
```
