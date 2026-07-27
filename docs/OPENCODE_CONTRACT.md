# OpenCode Subprocess Contract

## Context

LoopForge v6 spawns `opencode` CLI subprocesses to perform code modifications inside project repositories.

## Execution Model

- **Command Pattern**: `opencode run --prompt "<TASK_PROMPT>" --path "<PROJECT_ROOT>"`
- **Fallback Mock Mode**: If `OPENCODE_MOCK=1` or `opencode` binary is missing, LoopForge simulates execution via local script runner.
- **Timeouts**:
  - Subprocess hard limit: 300 seconds (5 minutes)
  - Circuit Breaker: 3 consecutive failures trigger state lock
  - Retries: Up to 3 attempts with diagnostic feedback injected into prompt
- **Environment**: Secrets (e.g. `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`) passed securely through subprocess `env`.

## Return Format

OpenCode runner returns a structured result:
```python
@dataclass
class OpenCodeResult:
    exit_code: int
    stdout: str
    stderr: str
    changed_files: list[str]
    diff: str
    duration_seconds: float
```
