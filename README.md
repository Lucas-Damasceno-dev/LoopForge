# 🚀 LoopForge

**Automated Loop Engineering Engine for AI Agents**

LoopForge é um motor autônomo de Loop Engineering projetado para criar, executar, refatorar e monitorar ciclos de desenvolvimento orientados a IA com resiliência industrial, guardrails rigorosos, telemetria SQLite e observabilidade completa.

> **Versão atual:** 5.0.0
> **License:** MIT

---

## Funcionalidades

| Fase | Módulo | Status |
|---|---|---|
| **1** | Fundação & Sistema de Configuração (Node.js + TypeScript ESM + Zod) | ✅ |
| **2** | Harness de Validação Multi-Runner (bash, parser, formatter) | ✅ |
| **3** | Gerenciamento de Memória & Guardrails (Circuit Breaker, Lessons/Handoff) | ✅ |
| **4** | Provedores LLM, Skill Presets & Git Sandbox (OpenCode, fallback, auto-PR, bootstrap) | ✅ |
| **5** | Swarm Multi-Agente, TUI & RAG Local (indexação semântica com embeddings e cosseno) | ✅ |
| **6** | Auto-Refatoração, Web Dashboard, Self-Healing Tests & CI/CD Nativo | ✅ |
| **7** | Workspace Orquestrador, Security Scanner, Budget Guard, Local LLM, Telemetry & Wizard | ✅ |
| **8** | Docker Sandbox, Test Generator Multi-Stack, Release/Bot, Context Compressor, Loop Lock | ✅ |
| **9** | **Propostas de Melhoria (P1)**: Telemetria SQLite, Interactive Review Gate, Auto-Fix Security, Notificações Multi-canal (Email, Desktop, Webhook), Parallel Workspaces, Config Hot-Reload, Pipeline npm & CLI JSON Output | ✅ |

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

# Executar com revisão interativa antes do PR
loopforge run --create-pr --review

# Modo watch com hot-reload de configurações
loopforge run --watch
```

---

## CLI Reference

| Comando | Descrição |
|---|---|
| `init [directory]` | Inicializa `.loopforge.json`, memórias e skills templates |
| `run [directory]` | Executa o ciclo do Loop Engine (`--create-pr`, `--review`, `--auto`, `-w/--watch`, `--format json\|text`) |
| `bootstrap` | Gera suíte de testes baseline automaticamente |
| `generate-tests` | Gera suítes de teste unitário multi-stack (Node, Python, Rust) (`--dry-run`, `--format json\|text`) |
| `refactor <rule>` | Executa auto-refatoração com isolamento Git Sandbox |
| `release [version]` | Gera notas de lançamento semânticas e atualiza CHANGELOG.md |
| `workspace [manifest]` | Orquestra loops em múltiplos projetos (`--parallel`, `-c/--concurrency <n>`, `--format json\|text`) |
| `audit [directory]` | Scanner de segurança com auto-correção (`--fix`, `--format json\|text`) |
| `wizard [directory]` | Assistente interativo de configuração e onboarding |
| `replay <sessionId>` | Reproduz telemetria quadro-a-quadro de sessões passadas |
| `ui [directory]` | Inicia Web Dashboard em `http://localhost:3000` |
| `ci:setup` | Gera `.github/workflows/loopforge-ci.yml` com etapa CodeQL/Audit |
| `status [directory]` | Exibe painel de status de config, LLM, skills e memórias |

---

## Configuração

O LoopForge é configurado via arquivo `.loopforge.json` na raiz do projeto:

```json
{
  "projectName": "Meu Projeto",
  "version": "5.0.0",
  "harness": {
    "runners": [
      { "name": "Unit Tests", "type": "unit", "command": "npm test", "timeoutMs": 60000 },
      { "name": "Linter", "type": "linter", "command": "npm run lint", "timeoutMs": 30000 }
    ],
    "parallel": true,
    "stopOnFirstFailure": false
  },
  "guardrails": {
    "maxTotalIterations": 10,
    "maxConsecutiveFailures": 3,
    "maxBudgetUsd": 5.0,
    "maxCostPerIteration": 2.0,
    "requireCleanGit": true
  },
  "memory": {
    "lessonsFile": ".loopforge/lessons.md",
    "handoffFile": ".loopforge/handoff.md",
    "maxLessonsPrompt": 5
  },
  "notifications": {
    "webhookUrl": "https://discord.com/api/webhooks/...",
    "desktop": { "enabled": true },
    "email": {
      "enabled": false,
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "to": "dev@exemplo.com"
    }
  },
  "llm": {
    "provider": "opencode",
    "model": "deepseek-v3",
    "fallbackModel": "anthropic/claude-3-5-sonnet",
    "temperature": 0.2
  }
}
```

---

## Desenvolvimento & Testes

```bash
# Build
npm run build

# Testes
npm test

# Type-check
npm run check
```

- **26 arquivos** de teste em `tests/`
- **46/46 testes aprovados** (incluindo testes de RAG semântico, SQLite, paralelo, auto-fix e notificações)
- **0 erros** no build TypeScript (`tsc --noEmit`)
