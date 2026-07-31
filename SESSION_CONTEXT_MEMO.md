# 📝 SESSION_CONTEXT_MEMO.md — LoopForge v6

**Data da Sessão**: 31 de Julho de 2026  
**Versão**: LoopForge v6.0.0  
**Objetivo**: Resumo executivo de conhecimentos, decisões arquiteturais, bugs corrigidos e mecanismos de resiliência implementados para servir de memória persistente em futuras sessões de desenvolvimento.

---

## 📌 1. Principais Descobertas e Decisões de Arquitetura

### 1.1 Resolução de Dependências Go no QA (`src/lf/pipeline/nodes/qa.py`)
- **Problema de Diagnóstico (`passou=0, erros=0`)**: Quando a LLM gera código em Go utilizando bibliotecas externas (ex: `github.com/gin-gonic/gin` ou `github.com/prometheus/client_golang`), o comando `go test ./...` falhava no passo de resolução de módulos, resultando em 0 testes executados (`passou=0, erros=0`) e forçando o loop de retry de 16 minutos sem sucesso.
- **Solução**:
  1. **Pre-fetch Automático**: `_run_harness` em `qa.py` executa `go mod tidy` antes do `go test ./...` sempre que detecta a stack `go` ou o arquivo `go.mod`.
  2. **Self-Healing Go**: Adicionado o auto-fix de dependências Go em `_attempt_dependency_self_healing`.

### 1.2 Resiliência LLM & Fallback Multi-Tier (`src/lf/runner/opencode/llm.py` & `llm_factory.py`)
- **Problema de Timeout**: Modelos de LLM no OpenRouter/OmniRoute (ex: `oc/deepseek-v4-flash-free`) atingem timeout em gerações extensas de código.
- **Solução**:
  1. **Retentativas com Backoff Exponencial**: 2 retentativas automáticas com tempo limite progressivo por tentativa (`call_openrouter_api`).
  2. **Fallback Universal de Subprocesso**: Removida a restrição de URL de modo que falhas em endpoints locais (OmniRoute) ou remotos executem o `OpenCodeRunner` em subprocesso automaticamente em vez de travar o pipeline.

### 1.3 Dogfooding Protection (`src/lf/pipeline/nodes/developer.py`)
- **Problema**: Execuções do `lf run` ou suítes de testes geravam arquivos que sobrescreviam o `pyproject.toml`, `AGENTS.md` e `.github/` na raiz do próprio repositório LoopForge.
- **Solução**: Implementado o detector de repositório `is_loopforge_repo` em `_write_project_files`. Qualquer escrita em pasta contendo `AGENTS.md` e `src/lf` bloqueia a alteração em arquivos de configuração do LoopForge (`PROTECTED_ROOT_FILES`).

### 1.4 Isolation de Worktree Sandbox (`src/lf/runner/git/sandbox.py`)
- O `GitSandbox` cria worktrees Git isoladas em `.slim/worktrees/task-<task_id>`.
- Merges na branch principal só ocorrem quando **QA + AppSec** aprovam a execução com sucesso.

### 1.5 Suíte de Testes de Snapshot dos Prompts (`tests/test_prompt_templates.py`)
- Prompts do `Developer` e `Tech Lead` possuem testes de snapshot garantindo regras de qualidade (tratamento rigoroso de erros sem `unwrap`/`panic!`, docstrings obrigatórias, Clean Architecture e `.env.example`).

---

## 🛠️ 2. Resumo das Implementações da Sessão

| Componente | Módulo | Descrição / Solução |
|---|---|---|
| **Self-Healing Go** | `qa.py` | Execução prévia e recuperativa de `go mod tidy` para garantir compilação e teste de pacotes Go. |
| **LLM Retries & Fallback** | `llm_factory.py` / `llm.py` | Retentativa com backoff exponencial e fallback para `OpenCodeRunner` em qualquer endpoint/modelo. |
| **Multi-Stack Gate** | `developer.py` | AST/Compilador roda `cargo check` (Rust), `go vet ./...` (Go), `node --check` (JS/TS) e `ast.parse` (Python). |
| **Self-Healing Cargo/NPM**| `qa.py` | Resolução de `requires rustc / edition2024` no `Cargo.toml` e `npm install --legacy-peer-deps`. |
| **Genome Seletivo** | `developer.py` | Injeção de símbolos filtrados por palavras-chave relevantes da `idea` e `stack`. |
| **Memória no TL** | `tech_lead.py` | O Tech Lead consulta o `MemoryManager` por lições aprendidas antes da tomada de decisão. |
| **Artefato Executivo** | `lessons.py` | `PROJECT_SUMMARY.md` com diagramas Mermaid, Badges do Shields.io e seções de Endpoints. |
| **CLI & Packaging** | `pyproject.toml` | Adicionadas dependências obrigatórias (`pydantic-settings`, `gitpython`, `alembic`, `langgraph-checkpoint-sqlite`). |

---

## 📊 3. Estatísticas da Suíte de Testes

- **Testes Unitários Ativos**: 152 testes em 35 arquivos (`tests/`).
- **Linter (Ruff)**: 100% aprovado (`select = ["E", "F", "W", "I", "N", "UP", "SIM"]`).
- **Verificador de Tipos (Mypy)**: 0 erros em 84 arquivos de código fonte.
- **Cobertura Geral**: **77.34%** (superando o limite mínimo de 75% exigido no CI).
