# LoopForge v6 — Plano de Migração e Arquitetura

> **Contexto:** Este documento define o plano completo de migração do LoopForge v5 (TypeScript, 5.200 linhas, 58 arquivos) para o LoopForge v6 (Python + LangGraph, ~3.200 linhas estimadas), integrando o The Foundry como ontologia de governança de agentes.
>
> **Stack:** Python 3.12+, LangGraph, Pydantic v2, Click, Rich, GitPython, SQLite
> **Orquestração:** LangGraph StateGraph com 5+ nós de agente + router centralizado
> **Execução:** LLM via LangChain para nós cognitivos; subprocesso OpenCode para nó Developer
> **Governança:** The Foundry (personas, schemas JSON, state machine, enums) carregado em runtime
> **Persistência:** SQLite (checkpoint LangGraph + telemetria própria)
> **Modelo alvo:** Gemini 3.6 Flash (via LangChain Google GenAI ou OpenRouter)
>
> **Aproveitamento:** ~700 linhas do Foundry MVP Python existente + ~1.500 linhas portadas do LoopForge TS + ~1.000 linhas novas
> **Cronograma:** ~12 dias úteis (~2.5 semanas), validado por 3 Oracle Gates
>
> **Status:** ✅ APROVADO COM ALTERAÇÕES (Oracle Review em 2026-07-26)
> **Revisor:** Oracle Agent (@oracle)
> **Alterações principais:** Merge F2+F3, split F1, delete 4 módulos redundantes, opencode.py movido para F2+3, gates reduzidos de 4 para 3

## Filosofia

LoopForge não executa tarefas. LoopForge gerencia agentes que executam tarefas.

LangGraph orquestra o pipeline de agentes. OpenCode executa trabalho técnico real.
The Foundry é o playbook de governança — personas, artefatos, transições de estado.

## Domain Model (Python)

```python
@dataclass
class Project:
    id: str
    vision: dict
    stack: TechStack
    plan: Plan
    state: ProjectState

@dataclass
class Plan:
    tasks: list[Task]
    graph: dict

@dataclass
class Task:
    id: str
    title: str
    status: Literal['pending', 'running', 'validating', 'failed', 'done']
    agent_id: str
    input: Artifact
    expected_schema: str
    prompt: str
    attempts: int = 0
    max_retries: int = 3
    depends_on: list[str]

@dataclass
class Artifact:
    id: str
    schema_id: str
    data: dict
    path: str
    hash: str

@dataclass
class AgentProfile:
    id: str
    role: str
    mission: str
    responsibilities: list[str]
    triggers: list[str]
    tools: list[str]
    failure_strategy: dict
    communication_protocol: dict
```

## Fases Revisadas (Pós-Oracle)

### Fase 0: Setup do Projeto Python (1 dia)
pyproject.toml, scaffold, logging estruturado (Rich) desde o início

### Fase 1a: Ontologia Essencial (1 dia)
Schemas Pydantic + personas registry APENAS. State machine labels/engine diferido.

### Fase 2+3: Pipeline + Orquestração (3 dias) [MERGE]
Merge de pipeline e orquestração em fase única. Inclui opencode.py (risco #1 prototipado cedo). Roteamento centralizado no router() do LangGraph.

———— Oracle Gate #1 ————

### Fase 4: Harness + Git (1.5 dias)
Portar runner, parser, formatter, bootstrap, checkpoint, sandbox, PR do TS

### Fase 1b: State Machine Labels (0.5 dia)
State definition + git labels — agora conectado ao Git que já existe

### Fase 5: Guardrails + SQLite + Budget (1 dia)
Circuit breaker (com budget embutido), loop lock, telemetria SQLite, memory manager. Analytics Chart.js diferido para pós-MVP.

———— Oracle Gate #2 ————

### Fase 6: CLI Final (1 dia)
4 comandos: init, plan, run, status. Replay vira flag `run --replay`.

### Fase 7: Integração + Testes (1.5 dias)
Pipeline completo. Teste end-to-end com Foundry. Documentação.

———— Oracle Gate #3 ————

## Oracle Gates Revisados

| Gate | Fases | Motivo |
|---|---|---|
| #1 | Após F2+3 | Pipeline + orquestração = cérebro. Precisam estar sólidos antes de conectar harness/CLI. |
| #2 | Após F5 | Integridade dos dados (SQLite) + segurança (guardrails). |
| #3 | Após F7 | Validação final do sistema completo. |

## Simplificações Aplicadas (Oracle Recommendations)

| Módulo | Ação | Motivo |
|---|---|---|
| `state_machine/engine.py` | ❌ DELETADO | LangGraph `SqliteSaver` já faz checkpoint/rollback nativo |
| `budget_controller.py` | ➕ ABSORVIDO em circuit_breaker.py | Budget é só mais uma condição de circuito aberto |
| `human_gate.py` | ❌ DELETADO | LangGraph `NodeInterrupt` nativo desde v0.2 |
| `personas/resolver.py` | ➕ ABSORVIDO em registry.py | 5-7 personas → dict lookup, não precisa de arquivo próprio |
| `telemetry/analytics.py` (Chart.js) | 🔻 DIFERIDO pós-MVP | Substituir por `rich.print` tabela + JSON export |
| `cli/commands/replay.py` | ➕ ABSORVIDO como `run --replay` | Reduz CLI para 4 comandos |

## Arquivos Finais (Python)

### Fase 0 — Setup
```
pyproject.toml
docs/ARCHITECTURE.md              # decisões arquiteturais
docs/OPENCODE_CONTRACT.md         # contrato de interface OpenCode-LoopForge
src/lf/__init__.py
src/lf/cli/__init__.py
src/lf/cli/main.py                # entrypoint click
src/lf/config/schema.py           # Pydantic models
src/lf/config/loader.py           # load/save JSON/YAML
```

### Fase 1a — Ontologia Essencial
```
src/lf/ontology/__init__.py
src/lf/ontology/schema_loader.py      # Carrega personas/schemas/enums do disco
src/lf/ontology/artifact_validator.py # Valida dicts contra Pydantic compilado
src/lf/ontology/personas/registry.py  # Catálogo de AgentProfile (com resolver embutido)
```

### Fase 2+3 — Pipeline + Orquestração (Merge)
```
src/lf/pipeline/__init__.py
src/lf/pipeline/graph.py              # StateGraph, router, build_graph
src/lf/pipeline/state.py              # GraphState TypedDict
src/lf/pipeline/llm_factory.py        # Factory de LLM (do Foundry MVP)
src/lf/pipeline/nodes/__init__.py
src/lf/pipeline/nodes/cpo.py          # CPO
src/lf/pipeline/nodes/pm.py           # PM
src/lf/pipeline/nodes/tech_lead.py    # TL
src/lf/pipeline/nodes/developer.py    # Dev (spawn OpenCode)
src/lf/pipeline/nodes/qa.py           # QA
src/lf/pipeline/nodes/appsec.py       # (futuro)
src/lf/pipeline/nodes/devops.py       # (futuro)
src/lf/runner/opencode.py             # Spawn OpenCode (movido p/ risco #1)
src/lf/orchestrator/__init__.py
src/lf/orchestrator/plan_creator.py   # Lê visão → tasks DAG
src/lf/orchestrator/task_dispatcher.py# Task → executa no pipeline
src/lf/orchestrator/iteration_manager.py # Retry + contexto
```

### Fase 4 — Harness + Git
```
src/lf/runner/harness/runner.py
src/lf/runner/harness/parser.py
src/lf/runner/harness/formatter.py
src/lf/runner/harness/bootstrap.py
src/lf/runner/git/checkpoint.py
src/lf/runner/git/sandbox.py
src/lf/runner/git/pr.py
```

### Fase 1b — State Machine Labels
```
src/lf/ontology/state_machine/definition.py
src/lf/ontology/state_machine/labels.py
```

### Fase 5 — Guardrails + Telemetria
```
src/lf/guardrails/circuit_breaker.py  # (com budget embutido)
src/lf/guardrails/loop_lock.py
src/lf/guardrails/security_scanner.py
src/lf/telemetry/recorder.py
src/lf/telemetry/store.py
src/lf/telemetry/analytics.py         # (simplificado: só tabela rich + JSON)
src/lf/memory/manager.py
```

### Fase 6 — CLI Final
```
src/lf/cli/commands/init.py
src/lf/cli/commands/plan.py
src/lf/cli/commands/run.py             # --replay embutido
src/lf/cli/commands/status.py
```

## Top 3 Riscos (pós-Oracle)

### Risco #1: Integração OpenCode
**Problema:** OpenCode é CLI interativa, não biblioteca. Pode travar sem input, levar 10min+, custar $.
**Mitigação:**
- Prototipar em F2+3 (teste unitário `test_opencode_spawn.py`)
- Contrato documentado em `docs/OPENCODE_CONTRACT.md` antes de codificar
- Timeouts em cascata: `subprocess (5min)` → `circuit breaker (3 falhas)` → `human gate (NodeInterrupt)`
- Modo mock com fixture + delay simulado

### Risco #2: "Deus Graph" (acoplamento)
**Problema:** Roteamento espalhado entre graph.py, dispatcher, iteration_manager.
**Mitigação:**
- Centralizar TODO roteamento no `router()` do LangGraph
- GraphState carrega tudo (task_id, attempt_count, feedback)
- Diagrama de estado explícito antes de implementar (1h de design)

### Risco #3: Foundry schema drift em runtime
**Problema:** Schemas JSON lidos em runtime. Mudança quebra sem type-check.
**Mitigação:**
- `schema_manifest.json` com version pinning
- Testes de integração que carregam TODOS schemas + validam mock data
- Graceful degradation: fallback pra schema hardcoded com warning

## Peças Adicionadas (pós-Oracle)

| Peça | Onde | Por quê |
|---|---|---|
| LLM Caching (SQLite) | F2+3 (llm_factory.py) | Foundry MVP já tem. Sem caching, retry re-invoca LLM = $. |
| Contrato OpenCode | `docs/OPENCODE_CONTRACT.md` (pré-F2+3) | Sem especificação, implementação é adivinhação. |
| Secret management | F0 (design) + F4 (impl) | API keys precisam chegar ao subprocesso OpenCode. |
| Caminho de migração | F0 (packaging: `lf` vs `loopforge`) | v5 TS atual funciona. Coexistência permite rollback. |
| Testes por fase | `tests/test_faseX.py` em cada fase | Sem testes por fase, F7 vira caixa-preta. |

## Cronograma Revisado

| Fase | Dias | Acumulado |
|---|---|---|
| **F0** — Setup Python | 1 | 1 |
| **F1a** — Ontologia Essencial | 1 | 2 |
| **F2+3** — Pipeline + Orquestração | 3 | 5 |
| Oracle Gate #1 | 0.5 | 5.5 |
| **F4** — Harness + Git | 1.5 | 7 |
| **F1b** — State Machine Labels | 0.5 | 7.5 |
| **F5** — Guardrails + SQLite | 1 | 8.5 |
| Oracle Gate #2 | 0.5 | 9 |
| **F6** — CLI Final | 1 | 10 |
| **F7** — Integração + Testes | 1.5 | 11.5 |
| Oracle Gate #3 | 0.5 | 12 |

**Total: ~12 dias úteis (~2.5 semanas)**
Redução de ~1.5 dia vs plano original (merges + cortes + 3 gates vs 4)

## Data Flow Final

```
usuário: loopforge init .
  → lê examples/the-foundry/ como ontology
  → pergunta stack, escopo, roadmap
  → gera .loopforge.json + plano DAG

usuário: loopforge run
  → pra cada task no DAG:
     1. task_dispatcher monta contexto (persona + input + schema)
     2. LangGraph pipeline executa sequência de nós:
        CPO: ideia → epic.json (Pydantic structured output)
          ↓
        PM: epic → user_stories.json (valida schema)
          ↓
        Tech Lead: user_stories → tech_spec.md (feedback loop com PM)
          ↓
        Developer: tech_spec → código REAL (spawn OpenCode)
          ↓ linha de comando opencode run --prompt "..."
          ↓ captura stdout, diff, exit code
          ↓
        QA: código → test_report (harness real: npm test / pytest / ...)
     3. Se falha → retry com feedback (max 3x)
     4. Se retries esgotados → human gate (NodeInterrupt)
  → ao final: git PR com labels Foundry + lessons.md + analytics

usuário: loopforge status
  → rich.print tabela com tasks, status, tempo, custo estimado

usuário: loopforge run --replay <session_id>
  → re-executa sessão anterior da telemetria SQLite
```

## Próximo Passo

Iniciar Fase 0 — Setup do Projeto Python.
