# 🚀 LoopForge

**Automated Loop Engineering Engine for AI Agents**

LoopForge é um motor autônomo de Loop Engineering projetado para criar, executar, refatorar e monitorar ciclos de desenvolvimento orientados a IA com resiliência industrial, guardrails rigorosos e observabilidade completa.

> **Versão atual:** 3.0.0
> **License:** MIT

---

## Funcionalidades

| Fase | Módulo | Status |
|---|---|---|
| **1** | Fundação & Sistema de Configuração (Node.js + TypeScript ESM + Zod) | ✅ |
| **2** | Harness de Validação Multi-Runner (bash, parser, formatter) | ✅ |
| **3** | Gerenciamento de Memória & Guardrails (Circuit Breaker, Lessons/Handoff) | ✅ |
| **4** | Provedores LLM, Skill Presets & Git Sandbox (OpenCode, fallback, auto-PR, bootstrap) | ✅ |
| **5** | Swarm Multi-Agente, TUI & RAG Local (pipelines de 4 papéis, indexação semântica) | ✅ |
| **6** | Auto-Refatoração, Web Dashboard, Self-Healing Tests & CI/CD Nativo | ✅ |

---

## Instalação

```bash
# Instalar globalmente via npm
npm install -g loopforge

# Ou usar diretamente com npx
npx loopforge --help
```

### Pré-requisitos

- **Node.js** >= 18 (ES2022)
- **Git** (para Git Sandbox e auto-PR)
- **GitHub CLI `gh`** (opcional, para criação de PRs)

---

## Quick Start

```bash
# Inicializar config, memórias e templates no repositório atual
loopforge init

# Inicializar com template de skills
loopforge init --template node-typescript

# Executar o ciclo do Loop Engine
loopforge run

# Executar com criação automática de PR
loopforge run --create-pr
```

---

## CLI Reference

| Comando | Descrição |
|---|---|
| `init [directory]` | Inicializa `.loopforge.json`, memórias e skills templates |
| `run [directory]` | Executa o ciclo do Loop Engine (Harness → Memória → Fallback → Git Sandbox) |
| `bootstrap` | Gera suíte de testes baseline automaticamente |
| `refactor <rule>` | Executa auto-refatoração com isolamento Git Sandbox |
| `ui [directory]` | Inicia Web Dashboard em `http://localhost:3000` |
| `ci:setup` | Gera `.github/workflows/loopforge-ci.yml` |
| `status [directory]` | Exibe painel de status de config, LLM, skills e memórias |

### Opções Globais

| Opção | Descrição |
|---|---|
| `-V, --version` | Exibe versão |
| `-h, --help` | Exibe ajuda |

### Opções por Comando

**`init`**
- `--template <name>` — Template de skills: `node-typescript`, `python-pytest`, `rust-cargo`

**`run`**
- `--create-pr` — Cria automaticamente um PR no GitHub após sucesso

**`ui`**
- `-p, --port <port>` — Porta do servidor (padrão: 3000)

---

## Configuração

O LoopForge é configurado via arquivo `.loopforge.json` na raiz do projeto:

```json
{
  "name": "Meu Projeto",
  "version": "1.0.0",
  "strategy": "creator",
  "harness": {
    "runners": [
      { "name": "Unit Tests", "type": "unit", "command": "npm test", "timeoutMs": 60000 },
      { "name": "Linter", "type": "linter", "command": "npm run lint", "timeoutMs": 30000 }
    ]
  },
  "guardrails": {
    "maxIterations": 10,
    "maxConsecutiveFailures": 3,
    "stopOnSuccess": true,
    "allowGitRollback": true
  },
  "memory": {
    "lessonsFile": ".loopforge/lessons.md",
    "handoffFile": ".loopforge/handoff.md",
    "autoUpdateLessons": true
  },
  "provider": {
    "name": "opencode",
    "model": "deepseek-v3",
    "enableModelFallback": true,
    "fallbackModel": "anthropic/claude-3-5-sonnet",
    "fallbackFailureThreshold": 2
  },
  "sandbox": {
    "enableBranchSandbox": true,
    "branchPrefix": "loopforge/task-"
  }
}
```

Veja [docs/configuration.md](docs/configuration.md) para a documentação completa do schema.

---

## Arquitetura

```
┌────────────────────────────────────────────────────┐
│                    CLI (Commander)                   │
│  init  run  bootstrap  refactor  ui  ci:setup  status │
└──────────┬────────────────────────────┬────────────┘
           │                            │
     ┌─────▼──────┐            ┌───────▼────────┐
     │  Loop Engine │            │ Refactor Engine │
     │  (orquestrador)│          │ (auto-refactor) │
     └──────┬──────┘            └────────────────┘
            │
    ┌───────┼───────────┬───────────────┐
    ▼       ▼           ▼               ▼
┌──────┐ ┌──────┐ ┌────────┐ ┌────────────┐
│Harness│ │Memory│ │Swarm   │ │   Git       │
│       │ │      │ │Agents  │ │  Sandbox    │
└──┬───┘ └──────┘ └───┬────┘ └──────┬─────┘
   │                  │             │
   ▼                  ▼             ▼
┌──────┐        ┌────────┐  ┌──────────┐
│Parser│        │  RAG   │  │PR Creator│
│Runner│        │ Local  │  │Checkpoint│
│Format│        │ Index  │  │          │
└──────┘        └────────┘  └──────────┘
```

Veja [docs/architecture.md](docs/architecture.md) para uma visão detalhada.

---

## Skill Presets

| Template | Descrição |
|---|---|
| `node-typescript` | Node.js + TypeScript + Vitest + ESLint/Biome |
| `python-pytest` | Python + Pytest + MyPy + Flake8 |
| `rust-cargo` | Rust + Cargo Test + Clippy + rustfmt |

---

## Exemplos

```
examples/basic-loop/    — Configuração funcional mínima com quality rules
```

```bash
cd examples/basic-loop
loopforge run
```

---

## Desenvolvimento

```bash
# Clonar
git clone <repo-url>
cd LoopForge

# Instalar dependências
npm install

# Build
npm run build

# Testes
npm test

# Type-check
npm run check
```

### Scripts Disponíveis

| Script | Comando |
|---|---|
| `npm run build` | `tsc` — Compila TypeScript para `dist/` |
| `npm test` | `vitest run` — Executa suíte de testes |
| `npm run test:watch` | `vitest` — Testes em modo watch |
| `npm run check` | `tsc --noEmit` — Type-check sem emitir |
| `npm start` | `node dist/cli/index.js` — Executa CLI |

---

## Testes

- **16 arquivos** de teste em `tests/`
- **30/30 testes aprovados**
- **0 erros e 0 warnings** no build (`tsc --noEmit`)
- Framework: **Vitest**

---

## Módulos

| Módulo | Descrição | Arquivos |
|---|---|---|
| `src/agents/` | Swarm multi-agente (Architect, Coder, Tester, Reviewer) | 2 |
| `src/ci/` | Integração contínua e webhooks (Slack/Discord) | 1 |
| `src/cli/` | Interface de linha de comando (Commander) | 7 |
| `src/config/` | Schema Zod e loader de configuração | 2 |
| `src/core/` | Loop Engine orquestrador + Refactor Engine | 2 |
| `src/git/` | Git Sandbox, PRs e Checkpoints | 3 |
| `src/guardrails/` | Circuit Breaker (3 falhas consecutivas) | 1 |
| `src/harness/` | Runner, Parser, Formatter, Bootstrap, Self-Healing | 6 |
| `src/indexer/` | RAG local de código (índice semântico) | 1 |
| `src/llm/` | Provedor LLM com fallback automático | 1 |
| `src/memory/` | Persistência de lessons.md e handoff.md | 1 |
| `src/skills/` | Templates e loader de skills | 3 |
| `src/ui/` | TUI interativa + Web Dashboard + Logger | 4 |

---

## Stack

| Camada | Tecnologia |
|---|---|
| Runtime | Node.js ≥ 18 (ESM) |
| Linguagem | TypeScript 5.5 (ES2022, strict) |
| CLI | Commander 12 |
| Validação | Zod 3.23 |
| Testes | Vitest 1.6 |
| LLM | OpenCode DeepSeek v4 + fallback Claude 3.5 Sonnet |
| CI | GitHub Actions (gerado automaticamente) |

---

## Documentação Complementar

- [Arquitetura Detalhada](docs/architecture.md)
- [Referência da CLI](docs/cli-reference.md)
- [Configuração](docs/configuration.md)
