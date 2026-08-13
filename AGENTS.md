# AGENTS.md — LoopForge v6

## CLI & Entrypoints

- Package: `lf`. Entry: `src/lf/cli/main.py` (Click group). Installed via `pip install -e .`.
- Main commands: `run`, `serve`, `benchmark`, `resume`, `diff`, `explore`, `pr`, `export`, `studio`, `init`, `plan`, `status`, `release`, `completion`, `generate-tests`, `audit`.
- `lf run --idea "..." --stack python --mock -i` is the most common invocation path.
- `lf serve --port 8000` starts FastAPI + WebSocket dashboard.

## Test & Verify

- Active test suite: `tests/` (107 files).
- Local & CI: `pytest tests/`. CI targets `tests/`.
- CI pipeline order: `ruff check --select E,F,W,I,N,UP,SIM src/lf tests` → `mypy src/lf` → `pytest --cov=src/lf --cov-fail-under=75 tests/`.
- CI matrix: Python 3.11 + 3.12.

## Architecture

- LangGraph `StateGraph` with nodes: **CPO → PM → Tech Lead → Test Writer → Developer → QA → Parallel Audit (AppSec + DevOps concurrently)** — `NodeRegistry` em `src/lf/pipeline/graph.py`: cpo, pm, tech_lead, test_writer, developer, qa, appsec, devops, parallel_audit. `lessons` **não é nó**: é função/artefato (`generate_lessons_md` em `src/lf/pipeline/nodes/lessons.py`) executado dentro do nó `parallel_audit`.
- Five routing modes (decided by `entry_router` in `graph.py`):
  - **full**: CPO→PM→TL→Dev→QA→Audit (default for features)
  - **fast**: Developer→QA→Audit (for bugfix/refactor/simple tasks)
  - **patch**: Developer→QA→Audit (patch/bugfix/simple — mesmo caminho do fast)
  - **review-only**: QA→Parallel Audit (task_type "review")
  - **explore**: Tech Lead spike (task_type "explore")
- Graph state: `src/lf/pipeline/state.py` (`GraphState` TypedDict) — além dos artefatos, declara canais `NotRequired`: `stack_rationale`, `security_report`, `devops_report`, `run_id`, `task_id`, `auto_create_devops_files`, `degraded`/`degraded_reason`, e o snapshot serializável `circuit_breaker`.
- Graph builder: `src/lf/pipeline/graph.py` — `build_graph()`, `router()`, `should_retry()`.
- After QA, `should_retry` decides: pass → parallel_audit, fail with retries left → developer, fail exhausted → parallel_audit (auditoria final + lessons; o erro de retries esgotados é gravado DENTRO do nó `parallel_audit` — `should_retry` é aresta condicional e não pode mutar estado).
- Parallel audit runs AppSec + DevOps simultaneously via `ThreadPoolExecutor`.

## Key Source Layout

| Path | Role |
|---|---|
| `src/lf/pipeline/nodes/*.py` | One file per agent persona (cpo, pm, tech_lead, test_writer, developer, qa, appsec, devops, parallel_audit) + `lessons.py` (função `generate_lessons_md` chamada por `parallel_audit`) |
| `src/lf/orchestrator/task_dispatcher.py` | `dispatch()` invokes graph, `resume()` from checkpoint, HITL handler |
| `src/lf/runner/opencode/runner.py` | `OpenCodeRunner` — spawns `opencode` subprocess via `script -q -c` |
| `src/lf/runner/harness/runner.py` | `TestHarnessRunner` — auto-detects test command from manifests |
| `src/lf/config/schema.py` | Pydantic models (TechStack, TaskSchema, LoopForgeConfig) |
| `src/lf/api/app.py` | FastAPI app factory, CRUD for runs, WebSocket streaming |
| `src/lf/pipeline/llm_factory.py` | `SQLiteLLMCache`, `compress_prompt()`, semantic normalization |

## LLM & Environment

- Primary provider: **OpenRouter** (`OPENROUTER_API_KEY`). Default model: `oc/deepseek-v4-flash-free`.
- Model default resolve via `resolve_default_model()` em `src/lf/pipeline/llm_factory.py:30` — precedência: `OPENROUTER_MODEL` → `OPENCODE_MODEL` → config `llm_model` → constante `DEFAULT_LLM_MODEL`. Sem fallback GenAI/Google.
- Fallback de execução: subprocesso `opencode` quando o provider HTTP falha; mock via `--mock` flag ou `OPENCODE_MOCK=1`. Quando set ou `opencode` binary not found, retorna mock responses (no subprocess).
- OpenCode subprocess uses: `script -q -c "opencode run 'PROMPT' -m MODEL --dir {root} --pure" /dev/null` — `--dir` força o chdir do opencode para o output_dir da run.
- Timeout do subprocesso mata a ÁRVORE inteira de processos (killpg + descendentes via /proc), não só o `script`.
- Timeout cascades: subprocess 5min (configurável em ade.yaml `runner.subprocess_timeout_seconds`) → circuit breaker (5 falhas consecutivas OU 20 iterações OU custo máximo; reset 300s p/ half-open) → human gate (NodeInterrupt).

## Runtime Config & Data

- Config: `.loopforge.json` — loaded/saved by `src/lf/config/loader.py` (supports JSON and YAML).
- AdeConfig: `.loopforge/ade.yaml` (via `load_ade_config` em `src/lf/config/loader.py`) — governa budget (`budget.max_usd`, fonte única do CircuitBreaker), HITL (`hitl.timeout_seconds`, `hitl.on_timeout`), runner (`runner.subprocess_timeout_seconds`, `runner.max_concurrent_runs`) e `api_keys` RBAC. Arquivo ausente → `AdeConfig()` com defaults.
- Checkpoints (trajectories): `.loopforge/trajectories.db` (LangGraph `AsyncSqliteSaver` — ativo desde a ADE). `.loopforge/checkpoints.sqlite` (~66 MB) é arquivo **legado** da época do `SqliteSaver`: o engine não o usa mais; NÃO apagar, apenas ignorar (`.loopforge/` é gitignored).
- LLM cache: `.loopforge/llm_cache.sqlite` — chave SHA256 de `model|temperature|prompt` (normalizado semanticamente), TTL 30 dias (`.loopforge/` gitignored; shared with `SQLiteLLMCache`).
- Telemetry: `.loopforge/telemetry.sqlite` (inclui `llm_costs` com `run_id`/`node` por run — base do `GET /runs/{id}/cost` e overrides em `budget_overrides`).
- Ontology: `examples/the-foundry/` (The Foundry — personas, schemas, state machine).
- Output artifact: `generated_code.py` at repo root (gitignored).

## Tech Stack Resolution (`resolve_tech_stack`)

Maps language → framework + test harness + package manager:

| Language | Framework | Test | PM |
|---|---|---|---|
| python | fastapi | pytest | pip |
| java | spring-boot | junit | maven |
| rust | actix | cargotest | cargo |
| go | gin | gotest | go |
| js/ts | express | vitest | npm |

TestHarnessRunner auto-detects from manifest files (pom.xml, Cargo.toml, go.mod, package.json, build.gradle).
QA node uses `TestHarnessRunner` to run tests.

## Human-in-the-Loop (HITL)

- Enabled via `-i` / `--interactive` flag.
- Gates interrupt at developer, qa, and parallel_audit nodes (configurable in `build_graph()`).
- Actions: approve, retry, adjust prompt (feedback category), adjust_state remoto (patch de estado via `POST /runs/{id}/decide`), continue, pause, abort.
- HITL timeout: 300s (configurável em `hitl.timeout_seconds`; comportamento no timeout: `on_timeout` default **continue** — opções: continue/abort/pause).
- Decisions recorded in `.loopforge/telemetry.sqlite` (`human_decisions` table).

## Conventions & Quirks

- **Language**: Portuguese for docs, comments, CLI output — maintain this.
- **Console output**: Uses `rich` (Console, Table, Syntax, Prompt).
- **Events**: `lf run` emite eventos WebSocket (`pipeline_started`, `node_execution`, `pipeline_finished`, `pipeline_failed`, `pipeline_error`, `pipeline_resumed`, `hitl_gate_reached`, `human_decision_expired`, `human_decision_submitted`, `token_delta`; a API emite `run_created`, `run_updated`). Seq por run é atômica (tabela `event_seq`, incremento via UPDATE...RETURNING em `src/lf/api/events.py`).
- **Status da run**: `queued` → `running` → `completed`/`failed`/`paused`; fila E3 controlada por `runner.max_concurrent_runs` (excedente fica `queued`).
- **Resume**: `lf resume` or `lf run --resume <task_id>` — loads checkpoint from `.loopforge/trajectories.db`.
- **Circuit breaker** in `TaskDispatcher` gates on `max_total_cost` from config `budget_limit_usd`.
- **Worktrees** managed in `.slim/worktrees/` — git worktrees for isolated feature work.
- **CI**: Ruff select rules are `E,F,W,I,N,UP,SIM` only. Mypy scans `src/lf` only. Coverage threshold: 75%.
- **Dependencies**: `uv.lock` present (managed by `uv`), but CI uses `pip install -e .`. No `setup.py`/`setup.cfg`. `pyproject.toml` tem `[project]` completo com deps (click, langgraph, langgraph-checkpoint-sqlite, pydantic, pydantic-settings, gitpython, alembic, rich, httpx, fastapi, uvicorn, aiosqlite, plyer, jinja2, mcp, pyyaml, tiktoken), extras `dev` (pytest, pytest-asyncio, pytest-cov, mypy, ruff), `[tool.ruff]` (line-length 120; select E,F,W,I,N,UP,SIM; ignore E501, SIM117, E402, F401), `[tool.mypy]` (mypy_path packages/*, ignore_missing_imports) — se adicionar dep, rode `uv add` e atualize `uv.lock`.
