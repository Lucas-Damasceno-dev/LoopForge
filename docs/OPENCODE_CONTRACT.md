# OpenCode CLI Contract

LoopForge communicates with OpenCode via subprocess. This document defines the contract.

## Invocation Format

```
opencode run "PROMPT_TEXT" -m MODEL --dir {root} --pure
```

- `PROMPT_TEXT`: The full prompt (system + user), passed as a single positional argument
- `-m MODEL`: Required model override (no default)
- `--dir {root}`: Forces opencode's chdir to the run output dir
- `--pure`: Enables pure mode (no tool-use overhead)
- Working directory: project root
- Timeout: **300s** default (configurable via `ade.yaml` `runner.subprocess_timeout_seconds`; `0` = no timeout; env `OPENCODE_TIMEOUT`)
- Wrapped with `script -q -c <cmd> /dev/null` to provide a PTY (required by opencode)
- On timeout, the **whole process tree** is killed (killpg + descendants via `/proc`), not just `script`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENCODE_MODEL` | `oc/deepseek-v4-flash-free` | Model to use (2nd in resolution chain; e.g. `opencode/deepseek-v4-flash-free`) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Custom base URL (e.g. local OmniRoute) |
| `OPENROUTER_TIMEOUT` | `300` | LLM HTTP timeout in seconds (`600` for reasoning models) |
| `OPENCODE_TIMEOUT` | — | Subprocess timeout override (seconds) |
| `OPENCODE_MOCK` | `0` | Set to `1` to return mock responses (no subprocess) |
| `OPENROUTER_API_KEY` | — | Primary provider API key (OpenRouter) |

## LLM Provider Resolution

The effective model is resolved by `resolve_default_model()` (`llm_factory.py:31`), in this priority:

1. `OPENROUTER_MODEL` env var
2. `OPENCODE_MODEL` env var
3. `llm_model` in `.loopforge.json` config
4. Default: `oc/deepseek-v4-flash-free` (`DEFAULT_LLM_MODEL`)

Primary provider is **OpenRouter** (HTTP direct). There is **no Google GenAI fallback**. When the HTTP call fails, execution falls back to the `opencode` subprocess; when `OPENCODE_MOCK=1` or the `opencode` binary is missing, mock responses are returned (no subprocess).

## Mock Mode

When `OPENCODE_MOCK=1` or `opencode` binary is not found on `$PATH`, the runner returns a mock `OpenCodeResult`:

```python
OpenCodeResult(
    exit_code=0,
    stdout="[MOCK OPENCODE] Executed prompt: ...",
    changed_files=[],
)
```

## Exit Codes

| Code | Meaning | Handling |
|---|---|---|
| `0` | Success | Parse stdout for JSON |
| `124` | Timeout | `TimeoutExpired` caught, retry or fail |
| `1` | Generic error | `RuntimeError` raised, captured in state |
| Other | Unknown | Treated as failure |

## Stdout Contract

LoopForge expects structured output. The `extract_json()` method tries:

1. **```json ... ``` block**: First attempt — regex extracts content between fenced code blocks
2. **Raw JSON**: If no fenced block found, attempts `json.loads()` on entire stdout

### JSON Schema Mode

When `schema_model` is provided (Pydantic model), the prompt is suffixed with:

```
Responda APENAS com um JSON válido que corresponda a este schema:
{model_json_schema()}
NÃO inclua texto explicativo, markdown, ou comentários.
Responda SOMENTE o objeto JSON puro.
```

Output is validated against the schema and cached.

## Caching

LLM responses are cached in `.loopforge/llm_cache.sqlite` (SHA256 keyed by full prompt). Cache is shared with `SQLiteLLMCache` in `llm_factory.py`.

- Cache key: `sha256(system_prompt + "\n\n" + user_prompt)`
- Cache table: `cache(prompt_hash TEXT PK, response TEXT, created_at TIMESTAMP)`
- Cache is opt-out: `call_llm_via_opencode(..., cache=False)`

## File Change Detection

After each OpenCode run, `detect_changed_files()` scans for new/modified files:

1. **Git status** (preferred): `git status --porcelain` — reports tracked changes
2. **mtime fallback**: glob `**/*` + compare `st_mtime` against run start time

### Ignored paths

```
.git, .loopforge, __pycache__, .pytest_cache, node_modules,
venv, .venv, .mypy_cache, .gemini
```

### Ignored files

```
generated_code.py, .loopforge.json, llm_cache.sqlite, .users.json, loop.lock
```

## Error Handling

| Scenario | Behavior |
|---|---|
| OpenCode binary not found | Fallback to mock mode (logged) |
| Subprocess timeout | Return `exit_code=124`, error message in stderr |
| JSON parse failure | `RuntimeError` with stdout preview (500 chars) |
| Pydantic validation failure | `ValidationError` from schema model constructor |
| General exception | Caught, returned as `OpenCodeResult(exit_code=1, stderr=str(e))` |

## Circuit Breaker Integration

When a `CircuitBreaker` is provided to `call_llm_via_opencode()`:

- Before spawning subprocess: `cb.can_proceed()` is checked
- If circuit is open: `RuntimeError("Circuit breaker is open")` is raised
- Must be explicitly passed; not required

## Security

- `opencode` must be on `$PATH` at invocation time
- No sandboxing beyond subprocess isolation
- Prompts may contain project source code — avoid logging in production
