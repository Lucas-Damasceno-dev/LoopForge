# 📋 Roadmap Checklist — LoopForge v6 Foundation & Quality Enhancement

> [!NOTE]
> Este documento é o plano diretor oficial de melhorias de arquitetura, qualidade de código e experiência do usuário para o **LoopForge v6**. Os itens estão organizados por ondas de execução prioritárias.
>
> **Status atualizado em 2026-08-12**: itens verificados no código real (grep/read). Evidências em `arquivo:linha`.

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

- [x] **2.1 Auto-Formatador no Nó QA (`cargo fmt`, `ruff format`, `gofmt`, `prettier`)**
  - O `TestHarnessRunner` executa o formatador automático da linguagem antes de rodar os testes unitários.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `qa.py:81-90` (gate de formatação: `format_issues` → erro de QA com feedback corrigível); `qa.py:249-253` (`_run_harness` chama `runner.run_format_check(target_dir)` **antes** de `runner.run()`); `runner.py:84` (`run_format_check`) e `runner.py:176` (`run`).
  - *Arquivos*: `src/lf/runner/harness/runner.py`, `src/lf/pipeline/nodes/qa.py`

- [x] **2.2 AppSec Ativo com Feedback Loop de Retentativa no Grafo**
  - Fechar o gap arquitetural no `graph.py` e `should_retry`: se o AppSec identificar vulnerabilidades de severidade CRÍTICA ou ALTA, ele envia feedback de segurança de volta ao nó Developer para refatoração.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `appsec.py:122-151` (`appsec_attempt = state+1`, `feedback_history` + mensagem de segurança, `next_agent="developer"` em :151); `parallel_audit.py:109-119` (propaga `appsec_attempt_count` + `feedback_history` do AppSec para o estado — antes descartados, causando loop); `graph.py:119` (aresta `parallel_audit: {developer, __end__}`). O Developer renderiza o feedback de segurança no prompt.
  - *Arquivos*: `src/lf/pipeline/graph.py`, `src/lf/pipeline/nodes/appsec.py`

- [x] **2.3 Gate Único de Qualidade e Validação Sintática no Developer**
  - Adicionar validação sintática rápida (`ast.parse` para Python, `node --check` para JS/TS, `cargo check` para Rust) dentro do nó Developer antes de repassar a entrega para o QA.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `developer.py:278` (`_check_syntax_and_types` — `ast.parse` Python, `cargo check` Rust, `node --check` JS/TS); chamada em `developer.py:610` antes de entregar ao QA; `graph.py:116-118` (self-edge `developer → developer` quando o gate falha).
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

- [x] **2.4 Self-Healing MVP de Dependências Incompatíveis**
  - Detectar mensagens de incompatibilidade de versão de compilador/dependência no log de erro do QA (ex: `requires rustc X` ou `peer dependency conflict`) e tentar ajustar a versão no manifesto (`Cargo.toml`, `pyproject.toml`, `package.json`).
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `qa.py:354-457` `_attempt_dependency_self_healing` — Cargo (`cargo update --precise` :364-379, `edition 2024→2021` :381-391), NPM (`npm install --legacy-peer-deps` :393-402), pip Python (`ModuleNotFoundError` → `pip install` :404-432), Maven (`mvn dependency:resolve -q` :434-446), Go (`go mod tidy` :448-455). Gatilho em `qa.py:70-74` (re-executa o harness após self-heal).
  - *Arquivos*: `src/lf/pipeline/nodes/qa.py`, `src/lf/runner/harness/runner.py`

---

## 🧠 ONDA 3: Memória Global Cross-Project & Genome-Awareness

- [x] **3.1 Memória Global Cross-Project de Lições Aprendidas**
  - Armazenamento global de lições no SQLite central `.loopforge/telemetry.sqlite`.
  - Busca por keyword score por stack e injeção automática do Top 3-5 lições mais relevantes nos prompts do Tech Lead e Developer.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `manager.py:17` (`cross_project_enabled`), `manager.py:91,100` (flag `cross_project` na busca), `manager.py:157,163` (`search_relevant_lessons(query, stack, cross_project=...)`), `manager.py:196` (`format_lessons_for_prompt`); injeção no Developer em `developer.py:493-500` com `cross_project=cross_project_enabled()`.
  - *Arquivos*: `src/lf/memory/manager.py`, `src/lf/pipeline/nodes/developer.py`

- [x] **3.2 Injeção Seletiva do Codebase Genome no Developer**
  - Injetar seletivamente no prompt do Developer os símbolos/funções relevantes extraídos pelo `genome` ao trabalhar em um repositório pré-existente do usuário, evitando duplicação de código.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `developer.py:467-485` — `GenomeScanner` importado via `importlib.util.find_spec` (pula silenciosamente se o pacote `genome` estiver ausente), `selective_genome = "\n".join(filtered_lines[:40])` (:482), injetado como `=== CODEBASE GENOME SELETIVO (DNA do Repositório) ===` (:485).
  - *Arquivos*: `src/lf/pipeline/nodes/developer.py`

---

## 🛡️ ONDA 4: Isolação de Segurança & Experiência de Saída (UX/UI)

- [~] **4.1 Worktree Sandbox Isolation & Proteção de Ambiente** *(parcial)*
  - Executar a geração e testes do projeto dentro de uma Git Worktree isolada (`.slim/worktrees/`).
  - Efetuar o merge na branch principal apenas após a aprovação combinada do QA e do AppSec.
  - *Status*: ⚠️ **PARCIAL** (auditado 2026-08-12).
  - *Evidência*: `WorktreeSandbox` **existe** em `src/lf/runner/git/sandbox.py` (`create_worktree`/`merge_worktree`/`cleanup_worktree`, worktrees em `.slim/worktrees/`), **mas não é referenciado** pelo `TaskDispatcher` nem pela CLI (grep por `WorktreeSandbox`/`git.sandbox` em `src/lf/` só encontra o próprio arquivo). Falta conectar no `TaskDispatcher.dispatch()`.
  - *Arquivos*: `src/lf/runner/git/checkpoint.py`, `src/lf/orchestrator/task_dispatcher.py`

- [x] **4.2 Resumo Executivo em Markdown com Diagrama Mermaid (`PROJECT_SUMMARY.md`)**
  - Gerar um arquivo `PROJECT_SUMMARY.md` ao final da execução contendo um Diagrama Mermaid da Arquitetura gerada, badges de qualidade/segurança e instrução de comandos CLI/endpoints.
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `lessons.py:121-168` — `mermaid_diagram` (graph TD) em :122, `PROJECT_SUMMARY.md` gerado junto com `lessons.md` em cada diretório de output (:165-168).
  - *Arquivos*: `src/lf/pipeline/nodes/lessons.py`, `src/lf/orchestrator/task_dispatcher.py`

- [x] **4.3 Wizard Multi-Etapas TUI**
  - *Status*: ✅ **IMPLEMENTADO** (auditado 2026-08-12).
  - *Evidência*: `run.py:19` (`_run_interactive_wizard`), `run.py:128` (flag `--wizard`), `run.py:164` (auto-trigger quando `not idea and sys.stdin.isatty()`).
  - *Nota*: implementado com **Click prompts** (interativos), **NÃO** com `InquirerPy`/`questionary`.
  - *Arquivos*: `src/lf/cli/commands/run.py`

- [~] **4.4 Diff Side-by-Side Interativo no HITL (`lf run -i`)** *(parcial)*
  - *Status*: ⚠️ **PARCIAL** (auditado 2026-08-12).
  - *Evidência*: `lf diff` standalone **existe** (`diff.py:21` `diff_cmd`, `:33`/`:58` rendering side-by-side via `_render_side_by_side_diff`/`_render_side_by_side_files`), **mas não está integrado** ao fluxo HITL do `lf run -i`.
  - *Arquivos*: `src/lf/cli/commands/studio.py`, `src/lf/orchestrator/task_dispatcher.py`

---

## 📌 Milestone v7 (Parqueado para o Próximo Ciclo)

- [ ] **5.1 Entrega Incremental por User Story (Incremental Feature Slices)**
  - Reestruturação da topologia do grafo para ciclo iterativo `Developer ↔ QA` por User Story individual antes da agregação final.
  - *Status*: ⏳ **PENDENTE** (auditado 2026-08-12).
  - *Justificativa*: nenhum trecho de slice incremental (user-story granular) encontrado no código (`grep` por `incremental`/slice por user story não retorna matches); topologia atual é whole-feature (`Developer` entrega o projeto inteiro de uma vez).
