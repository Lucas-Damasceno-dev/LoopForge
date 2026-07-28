# OpenCode CLI Contract

LoopForge communicates with OpenCode via subprocess. This document defines the contract.

## Invocation Format

```
opencode run "PROMPT_TEXT" [-m MODEL]
```

- `PROMPT_TEXT`: The full prompt (system + user), passed as a single positional argument
- `-m MODEL`: Optional model override (default: `openrouter/openrouter/free`)
- Working directory: project root
- Timeout: 300s (configurable via `OpenCodeRunner(timeout_seconds=N)`)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENCODE_MODEL` | `openrouter/openrouter/free` | Model to use |
| `OPENCODE_MOCK` | `0` | Set to `1` to return mock responses (no subprocess) |
| `GEMINI_API_KEY` | — | API key for Google models (fallback path in `llm_factory.py`) |

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
