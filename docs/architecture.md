# Arquitetura

## Visão Geral

O LoopForge é estruturado em camadas concêntricas ao redor do **Loop Engine**, que orquestra ciclos de desenvolvimento autônomos. Cada camada é isolada por interfaces bem definidas, permitindo substituição de implementações sem impacto nas demais.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLI Layer                                     │
│  init  run  bootstrap  refactor  workspace  audit  wizard  replay    │
│  ui  ci:setup  status                                                 │
├─────────────────────────────────────────────────────────────────────┤
│                      Orchestration Layer                               │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │ Loop Engine  │  │ Refactor Engine  │  │ Workspace Orch.  │        │
│  │ (core/loop)  │  │ (core/refactor)  │  │ (core/workspace) │        │
│  └──────┬───────┘  └──────────────────┘  └──────────────────┘        │
├─────────┼───────────────────────────────────────────────────────────┤
│         │              Domain Services                                 │
│  ┌──────▼──────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │   Harness    │ │ Memory │ │  Swarm   │ │Security  │ │   Git    │ │
│  │ (validação)  │ │ (cache)│ │ (agentes)│ │ Scanner  │ │ (sandbox)│ │
│  └──────┬──────┘ └────────┘ └─────┬────┘ └──────────┘ └────┬─────┘ │
├─────────┼─────────────────────────┼────────────────────────┼───────┤
│         │       Infrastructure      │                        │        │
│  ┌──────▼──────┐ ┌──────────┐  ┌──▼──────────┐  ┌─────────▼─┐   │
│  │ LLM Provider │ │   RAG    │  │   Circuit    │  │  CI/CD    │   │
│  │ (+ Ollama)   │ │ (hash    │  │   Breaker    │  │ + Webhook │   │
│  │              │ │  cache)  │  │ (+ budget)   │  │           │   │
│  └─────────────┘ └──────────┘  └─────────────┘  └───────────┘   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │              Cross-Cutting: Telemetry Recorder              │   │
│  │      .loopforge/telemetry/{sessionId}.json → Replay CLI     │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Loop Engine (`src/core/loop-engine.ts`)

O **Loop Engine** é o coração do sistema. Executa ciclos de:

1. **Harness** — Valida o estado atual via runners configurados (testes, linter, typecheck, e2e)
2. **Parser** — Analisa falhas e extrai feedback estruturado
3. **Memory** — Consulta lições aprendidas e handoff da sessão anterior
4. **LLM** — Envia contexto + falhas ao provedor LLM para gerar correções
5. **Git Sandbox** — Isola mudanças em branch dedicada
6. **Model Fallback** — Escalona para modelo secundário se necessário
7. **Checkpoint** — Commita progresso

### Fluxo do Ciclo

```
┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
│ Harness  │───▶│  Parser  │───▶│ Memory  │───▶│  LLM    │
│ (testes) │    │(falhas) │    │(lessons)│    │(prompt) │
└─────────┘    └─────────┘    └─────────┘    └────┬────┘
                                                  │
┌─────────┐    ┌─────────┐    ┌─────────┐        │
│Checkpoint│◀───│ Sandbox │◀───│ Fallback│◀───────┘
│ (commit) │    │ (branch)│    │ (model) │
└─────────┘    └─────────┘    └─────────┘
```

---

## Harness de Validação (`src/harness/`)

Sistema multi-runner que executa comandos e estrutura falhas.

### Runner (`runner.ts`)
- Executa comandos bash com timeout
- Captura stdout/stderr de forma estruturada
- **Execução paralela**: runners configurados disparam simultaneamente via `Promise.all` (padrão: ativado)

### Parser (`parser.ts`)
- Parseia saídas de diferentes tipos de runner:
  - **unit**: frameworks de teste (Vitest, Jest, Pytest)
  - **linter**: eslint, biome, flake8, clippy
  - **typecheck**: tsc, mypy
  - **e2e**: Playwright
  - **custom**: formato genérico

### Formatter (`formatter.ts`)
- Converte falhas estruturadas em Markdown para prompt do LLM

### Bootstrap (`bootstrap.ts`)
- Geração autônoma de suíte de testes baseline
- Detecta estrutura do projeto e cria sensores

### Self-Healing (`self-healing.ts`)
- Identifica testes desatualizados ou mocks quebrados
- Corrige automaticamente sem intervenção manual

### Types (`types.ts`)
- `RunnerResult`: resultado estruturado de cada runner
- `HarnessExecutionSummary`: sumário da execução completa

---

## Swarm Multi-Agente (`src/agents/`)

Pipeline sequencial de 4 papéis especializados:

```
┌────────────┐   ┌────────┐   ┌────────┐   ┌──────────┐
│  Architect  │──▶│  Coder  │──▶│ Tester  │──▶│ Reviewer │
│ (design)    │   │ (impl) │   │ (testes)│   │ (revisão)│
└────────────┘   └────────┘   └────────┘   └──────────┘
```

Cada papel recebe o output do anterior como contexto, formando um pipeline de qualidade progressiva.

---

## Git Sandbox (`src/git/`)

### Sandbox (`sandbox.ts`)
- Cria branch isolada: `loopforge/task-<timestamp>`
- Auto-merge no sucesso
- Rollback automático em falha

### PR Creator (`pr.ts`)
- Integração com GitHub CLI (`gh pr create`)
- Preenche título, corpo e labels automaticamente

### Checkpoint (`checkpoint.ts`)
- Commits parciais durante o ciclo
- Preserva histórico de tentativas

---

## LLM Provider (`src/llm/provider.ts`)

Sistema de provedor com fallback automático e suporte a LLMs locais:

| Provedor | Modelo | Uso |
|---|---|---|
| `opencode` (padrão) | DeepSeek v4 free | Ciclo normal |
| `ollama` | Modelo local (qwen2.5-coder, etc.) | Offline / custo zero |
| `openai` | GPT-4, GPT-3.5 | API externa |
| `anthropic` | Claude 3.5 Sonnet | API externa |
| `custom` | URL base customizada | Providers arbitrários |

### Ollama Local
- Conecta a `http://localhost:11434/api/generate`
- Custo $0.00, 100% offline
- Mapeia modelos automaticamente (deepseek* → qwen2.5-coder)

### Model Fallback
- Ativado quando falhas consecutivas atingem o limiar configurado (`fallbackFailureThreshold`, padrão: 2)
- Escalona para modelo secundário automaticamente

### Retry Exponencial com Jitter
- Trata erros temporários de rede e HTTP 429 (rate limit)
- Backoff exponencial com variação aleatória antes de ativar fallback

---

## Guardrails (`src/guardrails/`)

### Circuit Breaker (`circuit-breaker.ts`)
- Monitora falhas consecutivas, iterações totais e custo acumulado
- Três condições de abertura:
  - **Falhas**: `maxConsecutiveFailures` (padrão: 3)
  - **Iterações**: `maxTotalIterations` (padrão: 10)
  - **Orçamento**: `maxBudgetUsd` (padrão: $5.00) — trava financeira que interrompe o loop se o custo ultrapassar o limite

### Security Scanner (`security-scanner.ts`)
- Varredura estática de segurança no código-fonte
- Detecta:
  - **Secrets expostos**: chaves de API (sk-), tokens AWS (AKIA), JWT
  - **SQL Injection**: strings SQL concatenadas com template strings
  - **Código inseguro**: eval() e similares

### Proteções
- `requireCleanGit`: bloqueia execução se repo tem mudanças não commitadas
- `allowGitRollback`: reverte mudanças em caso de falha

---

## RAG Local (`src/indexer/rag.ts`)

Indexador semântico de código-fonte para repositórios grandes:

- Extrai símbolos (funções, classes, interfaces, tipos)
- Armazena em `.loopforge/index/symbols.json`
- **Cache incremental por hash SHA-256**: re-indexa estritamente arquivos modificados
- Permite consultas contextuais durante o ciclo do Loop Engine
- Reduz custo de LLM ao fornecer apenas contexto relevante

---

## Memory Manager (`src/memory/manager.ts`)

- Persistência de lições aprendidas em `.loopforge/lessons.md`
- Instruções de transição (handoff) em `.loopforge/handoff.md`
- **Git Diff Stat Semântico**: inclui no handoff o resumo `git diff --stat` das linhas alteradas no ciclo anterior
- Suporte a `maxLessonsPrompt`: limita quantidade de lições injetadas no prompt do LLM

---

## CI/CD e Webhooks (`src/ci/webhook.ts`)

### CI Setup (`loopforge ci:setup`)
- Gera `.github/workflows/loopforge-ci.yml`
- Pipeline configurado para rodar o Loop Engine em cada push

### Webhook Dispatcher
- Notificações para Slack e Discord
- Estado do ciclo (sucesso/falha/fallback ativo)

---

## Telemetry & Recorder (`src/telemetry/recorder.ts`)

- Grava histórico quadro-a-quadro da execução em `.loopforge/telemetry/{sessionId}.json`
- Cada frame contém: timestamp, iteração, papel do agente, modelo, se fallback está ativo, status do harness
- Reprodução em tempo real via `loopforge replay <sessionId>`

---

## Workspace Orchestrator (`src/core/workspace.ts`)

- Executa loops em lote através de múltiplos projetos
- Lê manifesto `loopforge-workspace.json` com lista de projetos
- Instancia `LoopEngine` para cada projeto sequencialmente
- Coleta resultados agregados por projeto

---

## CLI Wizard (`src/cli/commands/wizard.ts`)

- Assistente interativo de configuração e onboarding
- Sequência guiada: `init` (template Node/TS) → `bootstrap` → sumário final
- Ideal para novos usuários do LoopForge

---

## TUI, Web Dashboard & Logger (`src/ui/`)

### Terminal UI (`tui.ts`)
- Visualizador de progresso no terminal
- Barra de pass-rate
- Indicador de model fallback

### Web Dashboard (`server.ts`)
- Servidor local em `http://localhost:3000`
- Relatórios gráficos de execução
- Histórico de ciclos
- Métricas de custo

### Logger (`logger.ts`)
- Logger estruturado com níveis
- Saída formatada para terminal e arquivo

### Dashboard (`dashboard.ts`)
- Agrega dados de múltiplas execuções
- Métricas de performance e falhas
