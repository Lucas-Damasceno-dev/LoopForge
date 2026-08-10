# 📋 Roadmap Checklist — LoopForge v6 Foundation & Quality Enhancement

> [!NOTE]
> Este documento é o plano diretor oficial de melhorias de arquitetura, qualidade de código e experiência do usuário para o **LoopForge v6**. Os itens estão organizados por ondas de execução prioritárias.

---

## 🚀 ONDA 1: Correções de Prompt & Prompt Templates (Ganho Imediato / Baixo Esforço)

- [x] **1.1 Diretriz Estrita de Tratamento de Erros no Prompt do Developer**
  - Prompt proíbe `unwrap()`, `expect()`, `panic!` em Rust (exige `anyhow`/`thiserror`).
  - Prompt proíbe `except Exception: pass` ou `try/except` vazios em Python.
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

- [x] **1.2 Docstrings e Documentação Inline Obrigatórias no Prompt**
  - Prompt exige que todas as funções e métodos públicos possuam docstrings estruturadas no padrão nativo da linguagem (`///` em Rust, `"""` em Python, `/** */` em TypeScript).
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

- [x] **1.3 Clean Architecture Idiomática por Stack no Tech Lead**
  - Prompts do Tech Lead incluem os templates de estrutura de diretórios esperados para cada stack:
    - Rust: `src/domain/`, `src/adapters/`, `src/ports/`, `src/entrypoints/`
    - Python: `src/core/`, `src/services/`, `src/api/`, `src/repositories/`
  - *Arquivos*: `src/lf/pipeline/nodes/tech_lead.py`

- [x] **1.4 Módulo de Configuração Tipado + `.env.example`**
  - Projetos gerados incluem automaticamente um módulo de configuração tipado (`pydantic-settings` / `dotenv`) e um arquivo `.env.example`.
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

---

## ⚡ ONDA 2: Qualidade de Resultado & Fechamento de Gaps de Grafo (Alta Prioridade)

- [ ] **2.1 Auto-Formatador no Nó QA (`cargo fmt`, `ruff format`, `gofmt`, `prettier`)**
  - O `TestHarnessRunner` executa o formatador automático da linguagem antes de rodar os testes unitários.
  - *Arquivos*: `src/lf/runner/harness/runner.py`, `src/lf/pipeline/nodes/qa.py`

- [ ] **2.2 AppSec Ativo com Feedback Loop de Retentativa no Grafo**
  - Fechar o gap arquitetural no `graph.py` e `should_retry`: se o AppSec identificar vulnerabilidades de severidade CRÍTICA ou ALTA, ele envia feedback de segurança de volta ao nó Developer para refatoração.
  - *Arquivos*: `src/lf/pipeline/graph.py`, `src/lf/pipeline/nodes/appsec.py`

- [ ] **2.3 Gate Único de Qualidade e Validação Sintática no Developer**
  - Adicionar validação sintática rápida (`ast.parse` para Python, `node --check` para JS/TS, `cargo check` para Rust) dentro do nó Developer antes de repassar a entrega para o QA.
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

- [ ] **2.4 Self-Healing MVP de Dependências Incompatíveis**
  - Detectar mensagens de incompatibilidade de versão de compilador/dependência no log de erro do QA (ex: `requires rustc X` ou `peer dependency conflict`) e tentar ajustar a versão no manifesto (`Cargo.toml`, `pyproject.toml`, `package.json`).
  - *Arquivos*: `src/lf/pipeline/nodes/qa.py`, `src/lf/runner/harness/runner.py`

---

## 🧠 ONDA 3: Memória Global Cross-Project & Genome-Awareness

- [ ] **3.1 Memória Global Cross-Project de Lições Aprendidas**
  - Armazenamento global de lições no SQLite central `.loopforge/telemetry.sqlite`.
  - Busca por keyword score por stack e injeção automática do Top 3-5 lições mais relevantes nos prompts do Tech Lead e Developer.
  - *Arquivos*: `src/lf/memory/manager.py`, `src/lf/pipeline/nodes/developer.py`

- [ ] **3.2 Injeção Seletiva do Codebase Genome no Developer**
  - Injetar seletivamente no prompt do Developer os símbolos/funções relevantes extraídos pelo `genome` ao trabalhar em um repositório pré-existente do usuário, evitando duplicação de código.
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

---

## 🛡️ ONDA 4: Isolação de Segurança & Experiência de Saída (UX/UI)

- [ ] **4.1 Worktree Sandbox Isolation & Proteção de Ambiente**
  - Executar a geração e testes do projeto dentro de uma Git Worktree isolada (`.slim/worktrees/`).
  - Efetuar o merge na branch principal apenas após a aprovação combinada do QA e do AppSec.
  - *Arquivos*: `src/lf/runner/git/checkpoint.py`, `src/lf/orchestrator/task_dispatcher.py`

- [ ] **4.2 Resumo Executivo em Markdown com Diagrama Mermaid (`PROJECT_SUMMARY.md`)**
  - Gerar um arquivo `PROJECT_SUMMARY.md` ao final da execução contendo um Diagrama Mermaid da Arquitetura gerada, badges de qualidade/segurança e instrução de comandos CLI/endpoints.
  - *Arquivos*: `src/lf/pipeline/nodes/lessons.py`, `src/lf/orchestrator/task_dispatcher.py`

- [ ] **4.3 Wizard Multi-Etapas TUI com `InquirerPy`/`questionary`**
  - *Arquivos*: `src/lf/cli/commands/run.py`

- [ ] **4.4 Diff Side-by-Side Interativo no HITL (`lf run -i`)**
  - *Arquivos*: `src/lf/cli/commands/studio.py`, `src/lf/orchestrator/task_dispatcher.py`

---

## 📌 Milestone v7 (Parqueado para o Próximo Ciclo)

- [ ] **5.1 Entrega Incremental por User Story (Incremental Feature Slices)**
  - Reestruturação da topologia do grafo para ciclo iterativo `Developer ↔ QA` por User Story individual antes da agregação final.
