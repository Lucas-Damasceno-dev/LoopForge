# Arquitetura

## Visão Geral

O LoopForge é estruturado em camadas concêntricas ao redor do **Loop Engine**, que orquestra ciclos de desenvolvimento autônomos. Cada camada é isolada por interfaces bem definidas, permitindo substituição de implementações sem impacto nas demais.

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                              │
│  Commander-based: init, run, bootstrap, refactor, ui, ...    │
├─────────────────────────────────────────────────────────────┤
│                     Orchestration Layer                        │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────┐   │
│  │ Loop Engine  │  │ Refactor Engine  │  │ Web Dashboard  │   │
│  │ (core/loop)  │  │ (core/refactor)  │  │ (ui/server)    │   │
│  └──────┬───────┘  └──────────────────┘  └────────────────┘   │
├─────────┼───────────────────────────────────────────────────┤
│         │            Domain Services                           │
│  ┌──────▼──────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐   │
│  │   Harness    │ │ Memory  │ │  Swarm   │ │     Git      │   │
│  │ (validação)  │ │ (cache) │ │ (agentes)│ │  (sandbox)   │   │
│  └──────┬──────┘ └────────┘ └─────┬────┘ └──────┬───────┘   │
├─────────┼─────────────────────────┼─────────────┼───────────┤
│         │       Infrastructure      │             │            │
│  ┌──────▼──────┐  ┌──────────┐  ┌──▼────────┐ ┌─▼────────┐ │
│  │ LLM Provider │  │   RAG    │  │ Circuit   │ │  CI/CD   │ │
│  │ (fallback)   │  │ (indexer) │  │ Breaker   │ │ Webhook  │ │
│  └─────────────┘  └──────────┘  └───────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘
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

Sistema de provedor com fallback automático:

| Provedor | Modelo | Uso |
|---|---|---|
| `opencode` (padrão) | DeepSeek v4 free | Ciclo normal |
| `fallback` | Anthropic Claude 3.5 Sonnet | Após falhas consecutivas |

O fallback é ativado quando o número de falhas consecutivas atinge o limiar configurado (`fallbackFailureThreshold`, padrão: 2).

---

## Guardrails (`src/guardrails/circuit-breaker.ts`)

### Circuit Breaker
- Monitora falhas consecutivas do harness
- **Threshold**: 3 falhas consecutivas (configurável)
- **Ação**: Interrompe o ciclo e retorna estado de falha

### Proteções
- `maxIterations`: limite máximo de iterações (padrão: 10)
- `stopOnSuccess`: para ao primeiro ciclo bem-sucedido
- `allowGitRollback`: reverte mudanças em caso de falha

---

## RAG Local (`src/indexer/rag.ts`)

Indexador semântico de código-fonte para repositórios grandes:

- Extrai símbolos (funções, classes, interfaces, tipos)
- Armazena em `.loopforge/index/symbols.json`
- Permite consultas contextuais durante o ciclo do Loop Engine
- Reduz custo de LLM ao fornecer apenas contexto relevante

---

## CI/CD e Webhooks (`src/ci/webhook.ts`)

### CI Setup (`loopforge ci:setup`)
- Gera `.github/workflows/loopforge-ci.yml`
- Pipeline configurado para rodar o Loop Engine em cada push

### Webhook Dispatcher
- Notificações para Slack e Discord
- Estado do ciclo (sucesso/falha/fallback ativo)

---

## TUI e Web Dashboard (`src/ui/`)

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
