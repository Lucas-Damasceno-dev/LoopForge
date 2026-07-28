# LoopForge v6 — Architecture

## Overview

LoopForge is an automated loop engineering engine for AI agents. v6 is built in Python with LangGraph for stateful workflow orchestration.

## Module Map

```
lf/
├── cli/              # Click CLI (init, plan, run, status)
├── config/           # Pydantic settings, JSON/YAML loader
├── pipeline/         # LangGraph StateGraph, nodes, state
│   ├── graph.py      # build_graph() — centralized router + edges
│   ├── state.py      # GraphState TypedDict (22 fields)
│   ├── llm_factory.py# SQLiteLLMCache + legacy get_llm
│   └── nodes/        # Individual agent nodes
│       ├── cpo.py    # → Product Manager
│       ├── pm.py     # → Tech Lead
│       ├── tech_lead.py # → Developer
│       ├── developer.py # → QA
│       └── qa.py     # → FINISH
├── orchestrator/     # Task dispatch, plan creation
│   ├── task_dispatcher.py # Builds state, invokes graph, handles interrupts
│   └── plan_creator.py    # vision → TaskSchema[]
├── guardrails/       # CircuitBreaker, LoopLock, SecurityScanner
├── telemetry/        # SQLite store + analytics
├── runner/           # OpenCode subprocess, test harness, git
│   ├── opencode/     # OpenCodeRunner, call_llm_via_opencode
│   └── harness/      # TestHarnessRunner, parser
├── ontology/         # The Foundry schema loader + persona registry
├── memory/           # Simple JSON memory
└── contrib/          # Experimental: FastAPI dashboard
```

## Data Flow

```
lf init  →  .loopforge.json (config)
lf plan  →  PlanSchema (tasks)
lf run   →  TaskDispatcher → build_graph() → StateGraph.invoke()
               ↓
         cpo → pm → tech_lead → developer → qa → end
               ↓
         TelemetryRecorder → SQLite store
               ↓
         CircuitBreaker (per-task)
```

## Pipeline Flow

Each pipeline cycle processes one task through 5 LangGraph nodes:

| Node | Input | Output |
|---|---|---|
| CPO | idea | epic (Pydantic EpicSchema) |
| Product Manager | epic | user_stories (UserStoryList) |
| Tech Lead | user_stories | tech_spec (markdown) |
| Developer | tech_spec | code (generated via OpenCode subprocess) |
| QA | code | test_report (TestExecutionReport) |

Routing is centralized in `graph.py:router()`. QA decides retry vs finish via `should_retry()`.

## Key Design Decisions

- **Router único**: routing in graph.py only, not in dispatcher/nodes
- **Mock mode**: `mock_llm=True` returns mock data, no subprocess
- **Circuit Breaker**: wired into `call_llm_via_opencode` and per-task loop
- **SQLite cache**: `SQLiteLLMCache` in llm_factory.py (not opencode.py)
- **Checkpointing**: LangGraph SqliteSaver for persistent state recovery

## CLI Commands

| Command | Description |
|---|---|
| `lf init` | Generate .loopforge.json config |
| `lf plan` | Create task plan from vision |
| `lf run` | Execute task pipeline (mock, interactive) |
| `lf status` | Show task status from plan |
