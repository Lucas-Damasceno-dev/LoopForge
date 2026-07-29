# LoopForge v6 — Architecture & Technical Specifications

## Overview

LoopForge é um orquestrador autônomo de governança de agentes de IA construído em Python 3.12+ utilizando **LangGraph** para orquestração de workflow com estado (`GraphState`), **Pydantic v2** para validação estrita de dados, **FastAPI** para API REST e WebSockets, e o harness **OpenCode** para execução e LLM routing.

---

## Module Map

```text
src/lf/
├── api/              # Servidor FastAPI REST, WebSockets e templates HTML
│   ├── app.py        # Endpoints /api/runs, /ws/streaming, background workers
│   └── templates/    # Dashboard HTML/WebSockets interativo
├── cli/              # Interface CLI Click (main, run, serve, benchmark, resume, diff, explore, pr)
│   ├── commands/     # Módulos dos comandos individuais
│   └── main.py       # Registro centralizado de comandos core
├── config/           # Pydantic v2 schemas (LoopForgeConfig, TaskSchema, TechStack)
├── pipeline/         # LangGraph StateGraph, nodes, state
│   ├── graph.py      # build_graph() — Roteamento centralizado + arcos do grafo
│   ├── state.py      # GraphState TypedDict
│   ├── llm_factory.py# SQLiteLLMCache, compressão de prompt e normalização semântica
│   └── nodes/        # Nó individual dos agentes
│       ├── cpo.py            # → PM
│       ├── pm.py             # → Tech Lead
│       ├── tech_lead.py      # → Developer (decisão dinâmica de stack)
│       ├── developer.py      # → QA (geração multi-arquivo)
│       ├── qa.py             # → Parallel Audit (detecção automática de manifestos)
│       ├── parallel_audit.py # → AppSec + DevOps em paralelo via ThreadPoolExecutor
│       ├── appsec.py         # Scanner de segurança estático e auditoria LLM
│       ├── devops.py         # Análise de deployabilidade e CI/CD
│       └── lessons.py        # Gerador do artefato final lessons.md
├── orchestrator/     # Despacho de tarefas e criação de planos
│   ├── task_dispatcher.py # Constrói estado inicial, invoca o grafo e gerencia checkpoints
│   └── plan_creator.py    # Converte visão em TaskSchema[]
├── guardrails/       # CircuitBreaker e SecurityScanner
├── telemetry/        # Telemetria SQLite e benchmark ELO rating system
│   ├── benchmark.py         # Avaliação de benchmarks e cálculo ELO
│   └── benchmark_dataset.py # 10 problemas curados multi-stack
└── runner/           # Subprocesso OpenCode, git runner e test harness
    ├── opencode/     # OpenCodeRunner, call_llm_via_opencode
    └── harness/      # TestHarnessRunner
```

---

## Fluxo de Dados e Pipeline

```text
lf run --idea "..."
       ↓
TaskDispatcher → initial_state (stack=None)
       ↓
build_graph() → StateGraph.invoke()
       ↓
CPO → PM → Tech Lead (decide stack) → Developer (gera multi-arquivos) → QA (detecta & testa)
                                                                           ↓
                                                   Parallel Audit (AppSec + DevOps)
                                                                           ↓
                                                          Lessons Generator (lessons.md)
                                                                           ↓
                                                          FINISH / PR (gh pr create)
```

---

## Decisões de Design Principais

- **Decisão Dinâmica de Stack**: O Tech Lead analisa os requisitos e grava a melhor stack em `state["stack"]`. Se o usuário fornecer `--stack`, esta é usada como override.
- **Roteamento Centralizado no Grafo**: Arcos e transições definidos estritamente em `graph.py`.
- **Detecção Automática do QA**: Reconhecimento agnóstico de manifestos e executores (`pom.xml`, `Cargo.toml`, `go.mod`, `package.json`, `build.gradle`, `pyproject.toml`, `*.csproj`).
- **Auditoria Simultânea Paralela**: Nó `parallel_audit` executa `AppSec` e `DevOps` simultaneamente via `ThreadPoolExecutor` para otimização de tempo.
- **Isolamento de Sessão de Banco de Dados**: Trabalhadores assíncronos no FastAPI utilizam `session_factory()` próprio em corrotina background para evitar conflitos de concorrencia.
- **Cache Semântico e Compressão LLM**: Redução de custo via deduplicação de prompts e armazenamento local SQLite.
