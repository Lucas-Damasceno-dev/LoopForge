# AGENTS.md — LoopForge v6

## CLI & Entrypoints

- Package: `lf`. Entry: `src/lf/cli/main.py` (Click group). Installed via `pip install -e .`.
- Main commands: `run`, `serve`, `benchmark`, `resume`, `diff`, `explore`, `pr`, `export`, `studio`, `init`, `plan`, `status`, `release`, `completion`, `generate-tests`, `audit`.
- `lf run --idea "..." --stack python --mock -i` is the most common invocation path.
- `lf serve --port 8000` starts FastAPI + WebSocket dashboard.

## Test & Verify

- Active test suite: `tests/` (96 files).
- Local & CI: `pytest tests/`. CI targets `tests/`.
- CI pipeline order: `ruff check --select E,F,W,I,N,UP,SIM src/lf tests` → `mypy src/lf` → `pytest --cov=src/lf --cov-fail-under=75 tests/`.
- CI matrix: Python 3.11 + 3.12.

## Architecture

- LangGraph `StateGraph` with nodes: **CPO → PM → Tech Lead → Test Writer → Developer → QA → Parallel Audit (AppSec + DevOps concurrently)** — `NodeRegistry` em `src/lf/pipeline/graph.py`: cpo, pm, tech_lead, test_writer, developer, qa, appsec, devops, parallel_audit. `lessons` **não é nó**: é função/artefato (`generate_lessons_md` em `src/lf/pipeline/nodes/lessons.py`) executado dentro do nó `parallel_audit`.
- Two routing modes (decided by `entry_router` in `graph.py`):
  - **full**: CPO→PM→TL→Dev→QA→Audit (default for features)
  - **fast**: Developer→QA→Audit (for bugfix/refactor/simple tasks)
- Graph state: `src/lf/pipeline/state.py` (`GraphState` TypedDict).
- Graph builder: `src/lf/pipeline/graph.py` — `build_graph()`, `router()`, `should_retry()`.
- After QA, `should_retry` decides: pass → parallel_audit, fail with retries left → developer, fail exhausted → END.
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

- Primary provider: **OpenRouter** (`OPENROUTER_API_KEY`). Default model: `oc/deepseek-v4-flash-free` (or `OPENROUTER_MODEL`).
- Fallback: Google GenAI (`GEMINI_API_KEY`).
- Mock mode: `--mock` flag or `OPENCODE_MOCK=1`. When set or `opencode` binary not found, returns mock responses (no subprocess).
- OpenCode subprocess uses: `script -q -c "opencode run 'PROMPT' -m MODEL --pure" /dev/null`.
- Timeout cascades: subprocess 5min → circuit breaker (3 failures) → human gate (NodeInterrupt).

## Runtime Config & Data

- Config: `.loopforge.json` — loaded/saved by `src/lf/config/loader.py` (supports JSON and YAML).
- Checkpoints (trajectories): `.loopforge/trajectories.db` (LangGraph `AsyncSqliteSaver` — ativo desde a ADE). `.loopforge/checkpoints.sqlite` (~66 MB) é arquivo **legado** da época do `SqliteSaver`: o engine não o usa mais; NÃO apagar, apenas ignorar (`.loopforge/` é gitignored).
- LLM cache: `.loopforge/llm_cache.sqlite` (SHA256 keyed by prompt, shared with `SQLiteLLMCache`).
- Telemetry: `.loopforge/telemetry.sqlite`.
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
- Actions: approve, retry, adjust prompt (with feedback category), abort.
- HITL timeout: 300s (default behavior on timeout: abort).
- Decisions recorded in `.loopforge/telemetry.sqlite` (`human_decisions` table).

## Conventions & Quirks

- **Language**: Portuguese for docs, comments, CLI output — maintain this.
- **Console output**: Uses `rich` (Console, Table, Syntax, Prompt).
- **Events**: `lf run` emits WebSocket events (`pipeline_started`, `node_execution`, `pipeline_finished`).
- **Resume**: `lf resume` or `lf run --resume <task_id>` — loads checkpoint from `.loopforge/trajectories.db`.
- **Circuit breaker** in `TaskDispatcher` gates on `max_total_cost` from config `budget_limit_usd`.
- **Worktrees** managed in `.slim/worktrees/` — git worktrees for isolated feature work.
- **CI**: Ruff select rules are `E,F,W,I,N,UP,SIM` only. Mypy scans `src/lf` only. Coverage threshold: 75%.
- **Dependencies**: `uv.lock` present (managed by `uv`), but CI uses `pip install -e .`. No `setup.py`/`setup.cfg`. The `pyproject.toml` is minimal (build-system only) — if adding deps, update `uv.lock` via `uv add` or manually manage `pyproject.toml`.
