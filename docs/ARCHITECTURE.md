# LoopForge v6 Architecture

## Overview

LoopForge v6 is an autonomous software development orchestrator built with **Python 3.12+**, **LangGraph**, and **Pydantic v2**.
It integrates **The Foundry** ontology as runtime governance rules and uses **OpenCode** as the primary execution engine for hands-on code modification.

## Core Pillars

1. **Governance & Ontology (The Foundry)**
   - Personas: CPO, PM, Tech Lead, Developer, QA, AppSec, DevOps
   - Artifact Schemas: JSON/Pydantic validation for Epics, User Stories, Tech Specs, Test Reports
   - Enums & Conventions: ID formats, state transition labels

2. **Pipeline & Graph (LangGraph)**
   - `GraphState`: Shared state across all nodes (tasks, artifacts, attempts, feedback, status)
   - `StateGraph` pipeline: CPO -> PM -> Tech Lead -> Developer -> QA
   - Centralized `router`: Handles retry logic, human interrupts, and completion transitions

3. **Execution Engine (OpenCode Runner)**
   - Subprocess execution wrapper for OpenCode CLI (`opencode run`)
   - Structured stdout capture, execution diff generation, and error fallback

4. **Harness & Verification**
   - Automated testing harness running pytest/npm test/custom runners
   - Sandboxed git checkpoints and automated pull request generation

5. **Guardrails & Telemetry**
   - Circuit breaker with budget caps
   - Loop lock protection against infinite execution loops
   - SQLite persistent telemetry store and Rich CLI analytics
