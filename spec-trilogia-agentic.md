# 🧬🔗🧠 Trilogia Agentic — Spec Completa

> **Codebase Genome · Agentic Interface Registry · Agentic Retro**
>
> Três projetos no domínio de IA agentica para desenvolvimento de software.
> Validados contra o mercado (2026) — gaps genuínos, nada equivalente existe.

---

## Sumário

- [Visão Geral](#visão-geral)
- [Estratégia de Packaging](#estratégia-de-packaging)
- [1. 🧬 Codebase Genome](#1--codebase-genome)
  - [Proposta de Valor](#proposta-de-valor)
  - [Arquitetura](#arquitetura)
  - [CLI Reference](#cli-reference)
  - [Schema do Genoma](#schema-do-genoma)
  - [Árvore de Arquivos](#árvore-de-arquivos)
  - [Integração com LoopForge](#integração-com-loopforge)
  - [Métrica de Sucesso](#métrica-de-sucesso)
- [2. 🔗 Agentic Interface Registry](#2--agentic-interface-registry)
  - [Proposta de Valor](#proposta-de-valor-1)
  - [Arquitetura](#arquitetura-1)
  - [CLI Reference](#cli-reference-1)
  - [Schema do Registry](#schema-do-registry)
  - [Árvore de Arquivos](#árvore-de-arquivos-1)
  - [Integração com LoopForge](#integração-com-loopforge-1)
  - [Métrica de Sucesso](#métrica-de-sucesso-1)
- [3. 🧠 Agentic Retro](#3--agentic-retro)
  - [Proposta de Valor](#proposta-de-valor-2)
  - [Arquitetura](#arquitetura-2)
  - [CLI Reference](#cli-reference-2)
  - [Formato de Sessão (AgDR)](#formato-de-sessão-agdr)
  - [Árvore de Arquivos](#árvore-de-arquivos-2)
  - [Integração com LoopForge](#integração-com-loopforge-2)
  - [Métrica de Sucesso](#métrica-de-sucesso-2)
- [4. 🛠️ Módulos de Expansão & Arquitetura LoopForge](#4--módulos-de-expansão--arquitetura-loopforge)
  - [4.1 Roteamento Dinâmico de Escopo (`Router Node`)](#41-roteamento-dinâmico-de-escopo-router-node)
  - [4.2 Atribuição Heterogênea de Modelos](#42-atribuição-heterogênea-de-modelos)
  - [4.3 🔌 FlakeIsolator](#43--flakeisolator-disjuntor-de-testes-flaky-em-tempo-real)
  - [4.4 🧬 FailToEval](#44--failtoeval-gerador-de-benchmarks-nativos-de-regressão)
- [Roadmap](#roadmap)
- [Monorepo Híbrido — Estrutura Final](#monorepo-híbrido--estrutura-final)
- [FAQ](#faq)

---

## Visão Geral

### O Problema

O ecossistema de IA agentica para código ferveu em 2025-2026. Existem:

- **Agentes terminais**: Claude Code, Codex, OpenCode, Aider, Cline
- **IDEs agenticas**: Cursor, Devin, Copilot, Kiro
- **Orquestradores**: Orca (desktop), Paperclip (organizacional), Stoneforge
- **Pipelines autônomos**: LoopForge (7-agent DAG), MetaGPT
- **Code review**: CodeRabbit, Greptile, Qodo, DeepSource (20+ ferramentas)
- **Frameworks**: LangGraph, CrewAI, OpenAI SDK, Claude SDK
- **AgentOps**: AgentOps.ai, claudewatch
- **Convenção de código**: convention-learner, style-guide skill
- **Registro de decisões**: AgDR (padrão aberto)

**O que NÃO existe:**

1. Um perfil estrutural MULTIDIMENSIONAL do repositório que agentes consultem antes de agir
2. Um registro de contratos de interface entre agentes no mesmo codebase
3. Uma síntese pós-sessão que vira aprendizado realimentável no sistema

### A Solução

Três projetos que cobrem o ciclo completo: **conhecer → contratar → aprender**

```
                   ┌───────────────────┐
                   │  🧬 Codebase      │
                   │  Genome           │
                   │  (conhecer)       │
                   └───────┬───────────┘
                           │ consulta antes de agir
                           ▼
              ┌──────────────────────┐
              │  Agente faz mudança  │
              └──────┬───────────────┘
                     │ monitora interfaces
                     ▼
              ┌──────────────────────┐
              │  🔗 Interface        │
              │  Registry            │
              │  (contratar)         │
              └──────┬───────────────┘
                     │ detecta quebras
                     ▼
              ┌──────────────────────┐
              │  🔄 Ciclo completo   │
              └──────┬───────────────┘
                     │ análise pós-sessão
                     ▼
              ┌──────────────────────┐
              │  🧠 Agentic Retro    │
              │  (aprender)          │
              └──────┬───────────────┘
                     │ vira aprendizado
                     ▼
              ┌──────────────────────┐
              │  🧬 Codebase         │
              │  Genome (atualizado) │
              └──────────────────────┘
```

---

## Estratégia de Packaging

| Projeto | Onde nasce | Publicação | Prioridade |
|---|---|---|---|
| 🧬 **Genome** | Standalone CLI | PyPI independente + integração LF | 🔴 Alta (fundação) |
| 🔗 **Registry** | Dentro do LF | Extrai depois como independente | 🟡 Média |
| 🧠 **Retro** | Dentro do LF | Exporta formato AgDR, CLI depois | 🟢 Baixa |

**Decisão:** Monorepo com 3 pacotes publicáveis independentemente.

---

## 1. 🧬 Codebase Genome

### Proposta de Valor

Um repositório Python que gera e mantém um **perfil estrutural completo** de qualquer codebase — "o DNA do repositório". Qualquer agente (Claude Code, Codex, Cursor, OpenCode) pode consultar o genoma em **<2 segundos** em vez de gastar 5 minutos explorando.

### O que ele responde

- Quais são os padrões arquiteturais dominantes neste repositório? (clean arch, hexagonal, MVC, spaghetti)
- Qual o grau de acoplamento entre módulos?
- Quais arquivos são "ônibus" (baixa familiaridade, alta dependência)?
- Quais convenções implícitas existem? (naming, imports, error handling)
- O que mudou no genoma entre duas versões?

### Arquitetura

```
┌─────────────────────────────────────────────────┐
│                  genome CLI                     │
│  init  │  check  │  diff  │  serve  │  query    │
└────────┴────┬────┴────┬───┴─────────┴───────────┘
              │         │
     ┌────────▼──┐ ┌───▼────────┐
     │ Scanner   │ │ Checker    │
     │ AST +     │ │ Rule-based │
     │ Resolvers │ │ (.genomerc)│
     └────┬──────┘ └────┬───────┘
          │             │
     ┌────▼─────────────▼───────┐
     │        Core Layer        │
     │  Tree-sitter (AST)       │
     │  Symbol Resolvers        │
     │  NetworkX (grafo)        │
     │  SQLite (cache)          │
     └──────────────────────────┘
```

**Scanner & Symbol Resolvers** — caminha pela árvore do projeto, combina parsing via Tree-sitter com resolvedores de símbolos específicos por linguagem (ex: leitor de `tsconfig.json` para path aliases em TS, mapeador de módulos `__init__.py`/`sys.path` em Python) e extrai:
- Funções exportadas/privadas, classes, tipos, interfaces
- Importações resolvidas semânticamente (não apenas sintáticas)
- Estrutura de módulos e grafos de acoplamento real

**Checker** — compara um arquivo novo contra o genoma existente e as regras do `.genomerc`:
- Violações de camada (ex: módulo de infraestrutura importando do controller)
- Módulos de risco com alto acoplamento (*bus factor*)
- Desvios de métricas de código (ex: tamanho de função > mediana histórica do repositório)
- *Nota:* O `genome check` **não compete com linters/formatadores** (ESLint, Ruff). Ele foca exclusivamente em **convenções semânticas e arquiteturais de projeto**.

### Configuração Declarativa (`.genomerc`)

A detecção de padrão arquitetural induz sugestões estatísticas, mas a fonte da verdade pode ser declarada via `.genomerc`:

```toml
[architecture]
pattern = "clean-architecture"
layers = ["domain", "application", "infrastructure", "presentation"]

[[architecture.rules]]
from = "domain"
cannot_depend_on = ["infrastructure", "presentation"]

[[architecture.rules]]
from = "infrastructure"
cannot_depend_on = ["presentation"]

[metrics]
max_function_length_median_multiplier = 3.0
high_risk_dependent_threshold = 10
```

### CLI Reference

```bash
# Inicializar genoma do repositório atual
genome init .
# → Escaneia tudo, resolve símbolos e gera .genome/ na raiz

# Atualizar genoma incrementalmente (só arquivos modificados)
genome init --incremental

# Verificar se um arquivo novo viola regras arquiteturais do repositório
genome check ./src/new-feature.ts
# → Avisos Semânticos/Arquiteturais:
#   • camada: arquivo em 'domain' importa 'infrastructure/db.ts' (violação do .genomerc)
#   • complexidade: função de 120 linhas > 3x a mediana do repositório (25 linhas)
#   • acoplamento: acopla com módulo 'auth' que tem bus factor crítico (34 dependentes, 1 dono)

# Dump do genoma em múltiplos formatos (otimizado para LLMs)
genome dump --format markdown   # Visão limpa e densa para prompts de agentes (economiza tokens)
genome dump --format summary    # Resumo ultra-compacto (1/3 dos tokens)
genome dump --format json       # JSON completo para consumo por APIs/código

# Verificar diff arquitetural entre dois pontos
genome diff --since HEAD~3
# → Mudanças no genoma desde HEAD~3:
#   • +15 funções exportadas em src/api/
#   • acoplamento: módulo auth agora depende de billing (novo)

# Servir genoma como API HTTP/REST
genome serve --port 8080
# → GET /genome?format=markdown → genoma formatado para agentes
# → GET /check?file=src/x.ts → validação rápida

# Consultar genoma via interface determinística (SQL / DSL)
genome query --where "dependencies > 10"
genome query --sql "SELECT path, dependents_count FROM modules ORDER BY dependents_count DESC LIMIT 5"

# Opção com tradutor LLM (converte pergunta em linguagem natural para SQL determinístico)
genome query --llm "quais arquivos tem mais de 10 dependências?"
```

### Schema do Genoma

```json
{
  "version": "1.0.0",
  "repo": {
    "root": "/home/user/project",
    "langs": {
      "typescript": { "files": 142, "lines": 28400 },
      "python": { "files": 23, "lines": 4100 }
    },
    "total_files": 165,
    "total_lines": 32500
  },
  "conventions": {
    "error_handling": {
      "pattern": "result-type",
      "lib": "neverthrow",
      "usage_rate": 0.82
    },
    "testing": {
      "framework": "vitest",
      "location": "__tests__/",
      "naming": "{module}.test.ts"
    }
  },
  "modules": [
    {
      "path": "src/api",
      "exports": 23,
      "dependencies": ["src/auth", "src/db"],
      "dependents": ["src/web", "src/mobile"],
      "instability": 0.43
    }
  ],
  "architecture": {
    "pattern": "clean-architecture",
    "source": ".genomerc",
    "layers": ["domain", "application", "infrastructure", "presentation"],
    "layer_violations": [
      { "from": "src/domain/user.ts", "to": "src/infrastructure/repo.ts", "type": "illegal-boundary" }
    ],
    "circular_deps": [],
    "bus_factor": {
      "score": 0.65,
      "high_risk_files": [
        { "path": "src/core/engine.ts", "dependents": 34, "owners": 1 }
      ]
    }
  },
  "generated_at": "2026-07-29T20:30:00Z",
  "ttl_seconds": 86400
}
```

### Árvore de Arquivos

```
genome/
├── README.md
├── pyproject.toml                  # build + entrypoint genome CLI
├── genome/
│   ├── __init__.py
│   ├── __main__.py                 # python -m genome
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                 # click group (init, check, diff, serve, query, dump)
│   │   ├── cmd_init.py
│   │   ├── cmd_check.py
│   │   ├── cmd_diff.py
│   │   ├── cmd_dump.py
│   │   ├── cmd_serve.py
│   │   └── cmd_query.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── scanner.py              # Tree-sitter AST walker
│   │   ├── conventions.py          # Indução de convenções semânticas
│   │   ├── graph.py                 # NetworkX dependency graph
            ├── architecture.py         # Leitor de .genomerc e validador de camadas
│   │   ├── bus_factor.py           # Cálculo de bus factor
│   │   ├── renderers.py            # Formatadores (markdown, summary, json)
│   │   └── diff.py                 # Comparação entre genomas
│   ├── resolvers/                  # Resolvedores de Símbolos por Linguagem
│   │   ├── __init__.py
│   │   ├── base.py                 # SymbolResolver abstrato
│   │   ├── ts_resolver.py          # Leitor de tsconfig.json e path aliases
│   │   └── py_resolver.py          # Resolvedor de imports Python (__init__.py / sys.path)
│   ├── languages/
│   │   ├── __init__.py
│   │   ├── python.py               # Scanner específico Python
│   │   ├── typescript.py           # Scanner específico TS/TSX
        │   └── base.py                 # Scanner abstrato
│   ├── store/
│   │   ├── __init__.py
│   │   ├── sqlite.py               # Cache SQLite incremental
│   │   └── models.py               # Pydantic models do genoma
│   └── server/
│       ├── __init__.py
│       └── app.py                  # FastAPI (genome serve)
├── tests/
│   ├── test_scanner.py
│   ├── test_resolvers.py
│   ├── test_conventions.py
│   ├── test_graph.py
│   └── fixtures/                   # Repositórios de exemplo
└── .genome/                        # Gitignored — genoma cacheado
    └── genome.json
```

### Integração com LoopForge

| Pipeline Node | Como usa o Genome |
|---|---|
| **Tech Lead** | `genome check` na stack e arquitetura — valida regras de camadas do `.genomerc` |
| **Developer** | `genome dump --format markdown` injetado no prompt para entender o repositório em <2s |
| **QA** | `genome diff` para detectar violações arquiteturais introduzidas pela alteração |
| **AppSec** | `genome query --where "dependents > 10"` — identifica módulos críticos expostos |

```python
# Exemplo de integração no nó Developer
from genome import GenomeClient

genome = GenomeClient(path=".")
# Obtém resumo otimizado em Markdown para a janela de contexto da LLM
context_prompt = genome.dump(format="markdown")

# Injeta direto no System Prompt do agente de código
system_prompt = f"Você é um Developer Agent. Aqui está a estrutura do repositório:\n{context_prompt}"
```

### Métrica de Sucesso

- **genome init** escaneia repositório de 50K linhas em <30s
- **genome check** em arquivo novo leva <500ms
- Precisão de resolução de símbolos >90% em TypeScript e Python
- Formato Markdown enxuga mais de 60% dos tokens vs JSON cru
- Cache incremental: re-scan só arquivos modificados (git diff)


---

## 2. 🔗 Agentic Interface Registry

### Proposta de Valor

Um **registro central de contratos** que trackeia todas as interfaces públicas que agentes produzem e consomem (funções exportadas, tipos, APIs, schemas). Quando um agente muda uma interface (assinatura, nome, comportamento esperado), o Registry detecta consumidores quebrados e notifica ou auto-aplica migrações.

### O problema real

No LoopForge: o nó Developer gera `calculate_total(items: list[Item]) → float`. O nó QA escreve testes que chamam essa função. Um retry do Developer muda a assinatura para `calculate_total(items: list[Item], discount: float) → float`. O QA quebra **silenciosamente** — e não existe detecção disso hoje em nenhuma ferramenta.

### Arquitetura

```
┌───────────────────────────────────────────┐
│              registry daemon               │
│  track  │  check  │  diff  │  watch  │  serve │
└────┬────┴────┬────┴────┬───┴─────────┴──────┘
     │         │         │
┌────▼──┐ ┌───▼────┐ ┌──▼──────────┐
│Scanner│ │Checker │ │ Notifier    │
│ AST   │ │Contrato│ │ Slack/HTTP  │
└───┬───┘ └───┬────┘ └──────┬──────┘
    │         │             │
    └─────────┴─────────────┘
              │
     ┌────────▼────────┐
     │  Registry Store  │
     │  SQLite + JSON   │
     └─────────────────┘
```

**Scanner** — watch mode (inotify) que detecta mudanças em arquivos e re-extrai interfaces dos módulos afetados.

**Checker** — dado uma mudança de interface, busca no registry todos os consumidores e verifica se a mudança quebra o contrato.

**Notifier** — envia alertas (stdout, Slack webhook, HTTP POST, arquivo) quando uma quebra de contrato é detectada.

### CLI Reference

```bash
# Track interfaces do repositório (modo scan único)
registry track .

# Track em modo watch (fica observando mudanças)
registry track --watch

# Verificar se mudanças atuais quebram contratos
registry check
# → 🔴 BREAKING CHANGE detectada:
#   • calculate_total() mudou de 1 param → 2 params
#   • Consumidores afetados:
#     - src/tests/test_billing.py:12
#     - src/services/invoice.py:45

# Verificar um agente específico
registry check --agent developer
# → Verifica se as mudanças do developer desde o último commit quebram algo

# Ver diff de interfaces entre refs
registry diff --from HEAD~3 --to HEAD
# → Interfaces adicionadas: 12
# → Interfaces modificadas: 3 (2 breaking, 1 additive)
# → Interfaces removidas: 1

# Watch mode com notificação Slack
registry watch --notify webhook=https://hooks.slack.com/...

# Servir API REST
registry serve --port 8081
# → GET /interfaces → todas as interfaces
# → GET /interfaces/{modulo} → interfaces de um módulo
# → GET /check?agent=developer → verificação
```

### Schema do Registry

```json
{
  "version": "1.0.0",
  "interfaces": [
    {
      "id": "func_calculate_total",
      "kind": "function",
      "name": "calculate_total",
      "module": "src/services/billing",
      "signature": "(items: list[Item], discount?: float) -> float",
      "exported": true,
      "tags": ["public", "api"],
      "consumers": [
        { "file": "src/tests/test_billing.py", "line": 12, "agent": "qa" },
        { "file": "src/services/invoice.py", "line": 45, "agent": "developer" }
      ],
      "history": [
        { "version": "1.0.0", "signature": "(items: list[Item]) -> float", "agent": "developer", "commit": "abc123" },
        { "version": "2.0.0", "signature": "(items: list[Item], discount?: float) -> float", "agent": "developer", "commit": "def456" }
      ],
      "last_modified": "2026-07-29T18:00:00Z",
      "last_agent": "developer"
    }
  ],
  "modules": [
    {
      "path": "src/services",
      "interfaces_count": 8,
      "consumers": ["src/tests", "src/web"]
    }
  ],
  "breaking_changes": [
    {
      "interface_id": "func_calculate_total",
      "change": "parameter_added: discount",
      "impacted_consumers": 2,
      "detected_at": "2026-07-29T18:00:05Z"
    }
  ]
}
```

### Árvore de Arquivos

```
registry/
├── README.md
├── pyproject.toml                  # build + entrypoint
├── registry/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py                 # click group
│   │   ├── cmd_track.py
│   │   ├── cmd_check.py
│   │   ├── cmd_diff.py
│   │   └── cmd_watch.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── scanner.py              # Extração de interfaces via Tree-sitter
│   │   ├── tracker.py              # Watch mode (inotify)
│   │   ├── checker.py              # Verificação de contratos
│   │   ├── differ.py               # Diff entre snapshots
│   │   └── analyzer.py             # Análise de breaking change (additive vs breaking)
│   ├── store/
│   │   ├── __init__.py
│   │   ├── sqlite.py               # SQLite + snapshots
│   │   └── models.py               # Pydantic models
│   └── notifier/
│       ├── __init__.py
│       ├── base.py                 # Notifier abstrato
│       ├── stdout.py               # Log no terminal
│       ├── slack.py                # Webhook Slack
│       └── file.py                 # Arquivo JSON
├── tests/
│   ├── test_scanner.py
│   ├── test_checker.py
│   ├── test_tracker.py
│   └── fixtures/
│       ├── breaking_change/
│       └── additive_change/
└── .registry/                      # Gitignored
    ├── interfaces.json
    └── snapshots/
```

### Integração com LoopForge

```python
# Hooks injetados no pipeline

# Hook pós-Developer
def on_developer_complete(state: GraphState):
    registry = InterfaceRegistry(state.project_root)
    changes = registry.track()
    breaking = registry.check()
    if breaking:
        state.contract_breaks = breaking
        state.needs_attention = True  # Gate humano ou auto-fix

# Hook pós-QA
def on_qa_complete(state: GraphState):
    # Verificar se os testes cobrem as interfaces declaradas
    registry = InterfaceRegistry(state.project_root)
    missing = registry.uncovered_interfaces()
    if missing:
        logger.warning(f"Interfaces sem teste: {missing}")
        state.test_gap = missing
```

### Métrica de Sucesso

- Detecta 100% das quebras de contrato entre nós do pipeline
- Falso positivo <5% (detectar quebra onde não há)
- Scan de 1000 arquivos em <5s
- Watch mode com latência <2s entre mudança e detecção

---

## 3. 🧠 Agentic Retro

### Proposta de Valor

Ao final de cada execução de agente, o Retro captura automaticamente o que foi tentado, o que falhou, o que foi aprendido, e gera um relatório estruturado que alimenta execuções futuras. Não é um log — é uma **síntese inteligente** que identifica padrões, causas raiz de falhas, e recomendações para a próxima execução.

### O que ele extrai

- Qual foi o objetivo da sessão?
- Quais abordagens foram tentadas? Qual funcionou?
- Quanto tempo/gasto em cada abordagem?
- Quais erros recorrentes apareceram?
- O que deve ser feito diferente na próxima vez?

### Arquitetura

```
┌────────────────────────────────────────────┐
│              retro CLI                      │
│  start  │  end  │  analyze  │  feed  │  list │
└────┬────┴─────┬─┴──────┬────┴───────┬───────┘
     │          │        │            │
┌────▼──┐ ┌─────▼──┐ ┌──▼─────┐ ┌───▼───────┐
│Capture│ │Parser  │ │Analyzer│ │Recommender│
│Events │ │(AgDR)  │ │Patterns│ │Learnings  │
└───┬───┘ └───┬────┘ └───┬────┘ └─────┬─────┘
    │         │          │            │
    └─────────┴──────────┴────────────┘
              │
     ┌────────▼────────┐
     │  Session Store   │
     │  SQLite + JSONL  │
     └─────────────────┘
```

**Capture** — hook que escuta eventos do pipeline (node start, node end, retry, error, human gate) e registra em时序.

**Parser** — lê logs de sessão no formato AgDR (Agent Decision Records — padrão aberto existente).

**Analyzer** — identifica:
- Padrões de erro (erro X aconteceu 3 vezes em contextos similares)
- Abordagens mais eficientes (solução Y gastou 1/3 do custo da solução Z)
- Desvios de plano (objetivo era A, mas gastou 70% do tempo em B)

**Recommender** — gera recomendações acionáveis.

### CLI Reference

```bash
# Iniciar captura de sessão
retro start --session-id "lf-run-2026-07-29-001"

# Finalizar sessão e gerar relatório
retro end --session-id "lf-run-2026-07-29-001"
# → ✅ Relatório gerado: .retro/sessions/lf-run-2026-07-29-001/retro.md

# Analisar sessão existente (formato AgDR)
retro analyze ./sessao.jsonl
# → Resumo da Sessão
#   • Objetivo: "API REST em Rust com Axum"
#   • Duração: 4min32s
#   • Custo: $0.87
#   • Nós executados: 5/7 (AppSec+DevOps skipped — fast mode)
#   • Retries: 2 (QA falhou 2x, passou na 3ª)
#   • Padrões detectados:
#     - QA falhou por teste de integração sem DB mock (2x)
#     - Developer gerou código sem tratamento de erro no 1º try
#   • Aprendizado:
#     - Para projetos Rust, injetar "use thiserror" no prompt do Developer
#     - QA: adicionar "mock DB" como precondição
#   • Eficiência: 3 tentativas vs mediana histórica de 2.1

# Listar sessões
retro list
# → 15 sessões, últimas 3:
#   lf-run-2026-07-29-001   Rust API    PASS  4min  $0.87
#   lf-run-2026-07-28-003   Java CLI    FAIL  12min $2.10
#   lf-run-2026-07-28-002   Python Dash PASS  2min  $0.42

# Alimentar aprendizado no sistema (afeta próximas execuções)
retro feed --session-id "lf-run-2026-07-29-001"
# → Aprendizados registrados no cache:
#   • pattern: qa-db-mock → Rust projects → precondição injetada
#   • pattern: error-handling → first try → prompt.append("use thiserror")

# Sugerir melhorias para a próxima tarefa
retro suggest --next-task "CLI em Go com Cobra"
# → Com base em sessões anteriores com Go:
#   • Use o prompt template "go-cli-cobra" (sucesso em 4/5 tentativas)
#   • Evite flag --mock (causou falso positivo em 2 sessões Go)
#   • Orçamento estimado: $0.35-0.90
```

### Formato de Sessão (AgDR)

Baseado no padrão aberto [AgDR — Agent Decision Records](https://github.com/me2resh/agent-decision-record).

```jsonl
{"type": "session_start", "session_id": "lf-run-001", "goal": "API REST Rust Axum", "timestamp": "..."}
{"type": "decision", "agent": "tech_lead", "context": "Escolha de stack para API REST", "decision": "Rust + Axum + SQLx", "alternatives": ["Actix", "Tower"], "rationale": "Axum é mais idiomático no ecossistema tokio", "confidence": 0.8}
{"type": "node_start", "node": "developer", "attempt": 1, "timestamp": "..."}
{"type": "node_error", "node": "qa", "error": "integration test sem DB mock", "attempt": 1, "timestamp": "..."}
{"type": "node_retry", "node": "developer", "feedback": "Adicionar mock DB", "attempt": 2, "timestamp": "..."}
{"type": "node_success", "node": "qa", "attempt": 3, "timestamp": "..."}
{"type": "session_end", "session_id": "lf-run-001", "status": "PASS", "duration_ms": 272000, "cost": 0.87}
```

### Árvore de Arquivos

```
retro/
├── README.md
├── pyproject.toml
├── retro/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── cmd_analyze.py
│   │   ├── cmd_list.py
│   │   ├── cmd_feed.py
│   │   └── cmd_suggest.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── parser.py               # Lê formato AgDR → Session model
│   │   ├── analyzer.py             # Identifica padrões, eficiência, causas
│   │   ├── recommender.py          # Gera recomendações da sessão
│   │   └── historian.py            # Compara com sessões históricas
│   ├── store/
│   │   ├── __init__.py
│   │   ├── sqlite.py               # Sessões + métricas + aprendizado
│   │   └── models.py               # Pydantic models
│   └── report/
│       ├── __init__.py
│       ├── template.md             # Template do relatório markdown
│       └── renderer.py             # Gera retro.md formatado
├── tests/
│   ├── test_parser.py
│   ├── test_analyzer.py
│   ├── test_recommender.py
│   └── fixtures/
│       ├── session_pass.jsonl
│       ├── session_fail.jsonl
│       └── session_retry.jsonl
└── .retro/                         # Gitignored
    ├── sessions/
    └── learnings.json
```

### Integração com LoopForge

```python
# Hook final do pipeline
def on_pipeline_complete(state: GraphState):
    retro = Retro(project_root=state.project_root)
    
    # Finaliza captura da sessão atual
    report = retro.end(session_id=state.run_id)
    
    # Registra aprendizado
    retro.feed(report.learnings)
    
    # Se houver padrões de falha, ajusta prompts
    if report.patterns:
        state.prompt_overrides = report.patterns.to_overrides()
    
    # Anexa relatório como artefato
    state.artifacts.append(report.to_dict())
```

### Métrica de Sucesso

- Gera relatório em <1s após sessão finalizar
- Detecta padrões de erro com recall >70% nas top 3 causas raiz
- Recomendações levam a redução de 20%+ no número de retries (medido após 10 sessões)
- Compatível com formato AgDR padrão (qualquer ferramenta pode gerar logs)

---

## 4. 🛠️ Módulos de Expansão & Arquitetura LoopForge

### 4.1 Roteamento Dinâmico de Escopo (`Router Node`)

Para evitar latência e custo desnecessários em tarefas simples, o orchestrator do LoopForge utiliza um **`Router Node`** inicial que analisa o diff/escopo da tarefa e direciona a execução para sub-grafos otimizados:

| Modo de Roteamento | Nós Executados | Caso de Uso | Latência / Custo |
|---|---|---|---|
| 🩹 **`patch`** | `Developer` → `QA` | Correções de bug simples (1-5 linhas), ajustes de CSS ou typings | ~30s / $0.05 - $0.15 |
| 🔍 **`review-only`** | `QA` → `AppSec` | Auditoria e verificação de segurança em PRs gerados por humanos | ~1min / $0.20 - $0.40 |
| 🧠 **`explore`** | `Tech Lead` | Spikes de arquitetura, análise de viabilidade e trade-offs sem geração de código | ~45s / $0.10 - $0.25 |
| 🚀 **`full`** | `CPO` → `PM` → `Tech Lead` → `Dev` → `QA` → `AppSec` → `DevOps` | Novas features complexas, refatorações globais ou projetos do zero | ~4min / $0.80 - $2.50 |

### 4.2 Atribuição Heterogênea de Modelos

Para eliminar o efeito "Teatro de Agentes" (onde LLMs do mesmo provedor tendem a concordar passivamente umas com as outras), o LoopForge atrela modelos de provedores e arquiteturas distintas para personas diferentes:

- **CPO & PM:** `Gemini 2.5 Flash` (Janela de contexto massiva, rápido, excelente síntese de requisitos).
- **Tech Lead & Developer:** `Claude 3.5/3.7 Sonnet` ou `DeepSeek R1` (Raciocínio lógico e estrutural profundo para código e arquitetura).
- **QA:** `Claude Haiku` ou `OpenRouter (Fine-tuned QA)` (Rápido, rigoroso e instruído antagonicamente para quebrar o código).
- **Resultado:** A variação de vieses entre provedores quebra a câmara de eco e gera **antagonismo produtivo real**.

---

### 4.3 🔌 FlakeIsolator (Disjuntor de Testes Flaky em Tempo Real)

#### Proposta de Valor
Mapeia e isola oscilações/flakiness de ambiente em tempo real durante a execução do nó **QA**. Se um teste falha devido a ruído externo (race condition, timeout de rede, timestamp dinâmico), o `FlakeIsolator` impede que a falha entre no histórico do agente, evitando que ele desfaça código correto e queime tokens em loops de retry inúteis.

#### Como Funciona
1. O nó QA executa a suíte de testes e detecta uma falha em `test_user_session`.
2. O `FlakeIsolator` executa instantaneamente o mesmo teste em um sandbox isolado contra a branch limpa (`HEAD` sem as edições do agente).
3. Se o teste falhar no `HEAD` limpo ou demonstrar comportamento não-determinístico, ele é marcado como **`PRE-EXISTING FLAKE`**.
4. O erro é suprimido do loop do agente e substituído por uma notificação:
   > *"AVISO: O teste `test_user_session` falhou por oscilação de ambiente pré-existente (confirmado em HEAD). Ignorado para validação desta tarefa."*

---

### 4.4 🧬 FailToEval (Gerador de Benchmarks Nativos de Regressão)

#### Proposta de Valor
Converte automaticamente sessões de agentes que falharam ou exigiram intervenção humana em **suítes de benchmark de regressão reprodutíveis e nativas do próprio codebase**.

#### Como Funciona
1. Quando o `Agentic Retro` registra uma sessão que falhou ou que foi corrigida por um desenvolvedor humano via `NodeInterrupt`:
2. O `FailToEval` extrai o estado inicial do repositório, o prompt do usuário, a trajetória do agente que falhou e o diff final correto produzido pelo humano.
3. Transforma o caso em um mini-benchmark autocontido (formato SWE-bench / Inspect) integrado ao ELO benchmark interno do LoopForge.
4. Garante que futuras atualizações de prompts, modelos ou pipelines sejam validadas contra as falhas reais do passado no próprio repositório.

---

## 📋 Checklists de Implementação (ToDo)

### 🚀 Monorepo & Infraestrutura Inicial
- [x] Configurar workspace monorepo (`packages/genome`, `packages/registry`, `packages/retro`)
- [x] Configurar `pyproject.toml` base e resoluções de pacotes locais

### 1. 🧬 Codebase Genome (Fase 1)
- [x] **Data & Storage**: Implementar Pydantic Models (`store/models.py`) e Cache SQLite incremental (`store/sqlite.py`)
- [x] **Tree-sitter AST Walker**: Implementar `core/scanner.py` e parsers de linguagem (`languages/base.py`, `python.py`, `typescript.py`)
- [x] **Symbol Resolvers**: Resolvedor base (`resolvers/base.py`), Python (`py_resolver.py`) e TypeScript (`ts_resolver.py` / path aliases)
- [x] **Grafo de Dependências**: Grafo em NetworkX (`core/graph.py`) e cálculo de Bus Factor (`core/bus_factor.py`)
- [x] **Checker & `.genomerc`**: Validador de regras de camadas e limites arquiteturais (`core/architecture.py`)
- [x] **Convenções & Renderers**: Indução estatística de convenções (`core/conventions.py`), renderers (`markdown`, `summary`, `json`) e `core/diff.py`
- [x] **CLI & HTTP Server**: CLI Click (`genome init`, `check`, `diff`, `dump`, `serve`, `query`) e FastAPI REST server (`server/app.py`)
- [x] **Suíte de Testes**: Fixtures e testes automatizados em `packages/genome/tests/`

### 2. 🔗 Agentic Interface Registry (Fase 2)
- [ ] **Modelos & Storage**: Modelos de contrato e snapshot (`store/models.py`, `store/sqlite.py`)
- [ ] **Scanner de Interfaces**: Extração de assinaturas e funções exportadas via AST (`core/scanner.py`)
- [ ] **Detector de Breaking Changes**: Analisador de impacto de contrato (`core/analyzer.py`, `core/checker.py`, `core/differ.py`)
- [ ] **Watcher & Notifiers**: Monitor de arquivos (`core/tracker.py`) e notificadores (`stdout`, `slack`, `file`)
- [ ] **CLI & API**: CLI Click (`registry track`, `check`, `diff`, `watch`) e FastAPI server (`serve`)
- [ ] **Integração LoopForge**: Hooks no Tech Lead, Developer e QA em `src/lf/pipeline/nodes/`

### 3. 🧠 Agentic Retro (Fase 3)
- [ ] **Storage & AgDR Parser**: Parser de logs no formato AgDR (`core/parser.py`) e SQLite store (`store/sqlite.py`)
- [ ] **Analyzer & Recommender**: Análise de causa raiz/padrões (`core/analyzer.py`, `core/historian.py`) e gerador de sugestões (`core/recommender.py`)
- [ ] **Renderizador de Relatórios**: Template Markdown e gerador (`report/renderer.py`, `template.md`)
- [ ] **CLI**: CLI Click (`retro start`, `end`, `analyze`, `list`, `feed`, `suggest`)
- [ ] **Integração LoopForge**: Hook `on_pipeline_complete` em `src/lf/orchestrator/`

### 4. 🛠️ Módulos de Expansão & LoopForge Core (Fase 4)
- [ ] **Roteamento Dinâmico**: Implementar `Router Node` (`patch`, `review-only`, `explore`, `full`) em `src/lf/pipeline/`
- [ ] **Atribuição Heterogênea**: Mapeamento de LLMs antagônicos por persona
- [ ] **FlakeIsolator**: Disjuntor de testes flaky em tempo real no nó QA
- [ ] **FailToEval**: Gerador de benchmarks de regressão a partir de falhas/intervenções humanas

---

## Roadmap

### Fase 1 — MVP do Codebase Genome (semanas 1-3)

| Semana | Entregáveis |
|---|---|
| 1 | Scanner Python + TypeScript funcional. Extração de funções, classes, imports. |
| 2 | Indução de convenções (naming, imports, error handling). Cache SQLite. |
| 3 | CLI `init` + `check` + `diff`. Tests com fixtures de repositórios reais. |

**Gate:** `genome init` escaneia repositório 10K+ linhas e `genome check` detecta violações com <10% FP.

### Fase 2 — Registry + Integração Genome-LF (semanas 4-6)

| Semana | Entregáveis |
|---|---|
| 4 | Scanner de interfaces (Tree-sitter) + store SQLite. CLI `track` + `check`. |
| 5 | Watch mode + notifier (stdout, Slack). Breaking change detection. |
| 6 | Integração Genome + Registry no Tech Lead e QA nodes do LoopForge. |

**Gate:** Pipeline LoopForge detecta breaking changes entre Developer e QA em tempo real.

### Fase 3 — Retro + Ciclo Fechado (semanas 7-9)

| Semana | Entregáveis |
|---|---|
| 7 | Parser AgDR + analyzer (padrões, eficiência). CLI `analyze`. |
| 8 | Recommender + `retro feed` (aprendizado vira cache). Comparação histórica. |
| 9 | Integração Retro no pipeline LF. `retro suggest` funcional. |

**Gate:** Após 3 execuções do LF, Retro recomenda melhoria que reduz retries.

### Fase 4 — Polimento + Publicação (semanas 10-11)

| Semana | Entregáveis |
|---|---|
| 10 | Publicação PyPI (genome, registry, retro). Documentação completa. |
| 11 | Suporte a mais linguagens (Rust, Java, Go). Benchmarks públicos. |

---

## Monorepo Híbrido — Estrutura Final

```
loopforge/                          # Monorepo (pyproject.toml workspace)
├── pyproject.toml                  # Root workspace config
├── README.md
│
├── packages/
│   ├── genome/                     # codebase-genome no PyPI
│   │   ├── pyproject.toml
│   │   ├── genome/
│   │   └── tests/
│   │
│   ├── registry/                   # agentic-registry no PyPI (futuro)
│   │   ├── pyproject.toml
│   │   ├── registry/
│   │   └── tests/
│   │
│   └── retro/                      # agentic-retro no PyPI (futuro)
│       ├── pyproject.toml
│       ├── retro/
│       └── tests/
│
├── src/lf/                         # LoopForge — consome os 3 pacotes
│   ├── pipeline/nodes/
│   │   ├── cpo.py
│   │   ├── pm.py
│   │   ├── tech_lead.py           # → usa genome
│   │   ├── developer.py           # → registry observa
│   │   ├── qa.py                  # → registry verifica + genome diff
│   │   ├── appsec.py
│   │   ├── devops.py
│   │   └── lessons.py             # → retro alimenta
│   ├── orchestrator/
│   │   ├── plan_creator.py
│   │   ├── task_dispatcher.py
│   │   └── iteration_manager.py   # → retro hooks
│   └── runner/
│       └── opencode/
│
├── tests/
├── docs/
└── examples/
```

**Decisões de design:**

- Cada pacote em `packages/` tem `pyproject.toml` próprio, tests próprios, versão semântica própria
- LoopForge em `src/lf/` declara dependência `codebase-genome >= x.y` como qualquer outro pacote
- `packages/genome` é o primeiro a nascer standalone — já útil hoje sem LF
- `packages/registry` e `packages/retro` nascem dentro de `src/lf/` e são extraídos depois
- O workspace root `pyproject.toml` gerencia o monorepo (dica: usar `uv` como package manager)

---

## FAQ

### Esses projetos competem com ferramentas existentes?

**Codebase Genome:** Não compete com linters (ESLint, Ruff) porque não aplica regras fixas — ele INDUZ as convenções do repositório. Não compete com `convention-learner` (skill Claude Code) porque é standalone e qualquer agente consulta via CLI ou HTTP. É o "perfil estrutural" que faltava.

**Interface Registry:** Não compete com Pact (contrato de APIs HTTP entre serviços). Opera no nível de funções/tipos/módulos no MESMO repositório ou monorepo. É o "service mesh" para agentes de código.

**Agentic Retro:** Não compete com AgDR (padrão de formato) — pelo contrário, ADOTA o formato AgDR como entrada. É a camada de análise que ninguém construiu em cima do padrão.

### Por que Python? Não seria melhor TypeScript?

Python por 3 razões:
1. **Tree-sitter** (análise AST multiplataforma) tem bindings Python excelentes
2. **NetworkX** (grafos de dependência) — biblioteca mais madura em Python
3. **Sinergia com LoopForge** — já é Python + LangGraph. Se fossem TS, seriam projetos totalmente separados

### Preciso de um LLM para o Genome funcionar?

Não para o core. O Scanner é puramente AST-based (Tree-sitter) — zero LLM. A indução de convenções também é estatística (analisa frequência de padrões no codebase). LLM pode ser usado OPCIONALMENTE para:
- Descrição em linguagem natural do genoma ("descreva a arquitetura deste repositório")
- Sugestões de melhoria ("com base no genoma, recomendamos...")

### E se o repositório for monolíngue vs multilíngue?

O Genome detecta automaticamente as linguagens presentes e aplica os scanners correspondentes. Se encontrar uma linguagem sem scanner implementado, reporta como "não analisada" e continua com as demais.

### O Registry funciona fora do contexto de agentes?

Sim. Útil para qualquer time que queira rastrear interface drift em PRs — mesmo sem agentes envolvidos. O `registry check` funciona como um "type checker" para mudanças de interface entre branches.
