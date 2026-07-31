# 📝 SESSION_CONTEXT_MEMO.md — LoopForge v6

**Data da Sessão**: 31 de Julho de 2026  
**Versão**: LoopForge v6.0.0  
**Objetivo**: Resumo executivo de conhecimentos, decisões arquiteturais, bugs corrigidos e mecanismos de resiliência implementados para servir de memória persistente em futuras sessões de desenvolvimento.

---

## 📌 1. Principais Descobertas e Decisões de Arquitetura

### 1.1 Dogfooding Protection (`src/lf/pipeline/nodes/developer.py`)
- **Problema**: Execuções do `lf run` ou suítes de testes geravam projetos Python que sobrescreviam o `pyproject.toml`, `AGENTS.md` e `.github/` na raiz do próprio repositório LoopForge.
- **Solução**: Implementado o detector de repositório `is_loopforge_repo` em `_write_project_files`. Qualquer tentativa de gravar em uma pasta que contenha `AGENTS.md` e `src/lf` bloqueia a escrita em arquivos protegidos do repositório (`PROTECTED_ROOT_FILES`).

### 1.2 Isolation de Worktree Sandbox (`src/lf/runner/git/sandbox.py`)
- O `GitSandbox` cria worktrees Git isoladas em `.slim/worktrees/task-<task_id>`.
- Merges na branch principal só ocorrem quando **QA + AppSec** aprovam a execução com sucesso.

### 1.3 Suíte de Testes de Snapshot dos Prompts (`tests/test_prompt_templates.py`)
- Prompts do `Developer` e `Tech Lead` agora possuem testes de snapshot que garantem a presença continuada de diretrizes críticas (tratamento rigoroso de erros sem `unwrap`/`panic!`, docstrings obrigatórias, Clean Architecture e `.env.example`).

### 1.4 Resiliência LLM & Fallback Multi-Tier (`src/lf/runner/opencode/llm.py`)
- **Problema de Timeout**: Modelos gratuitos no OpenRouter/OmniRoute (ex: `oc/deepseek-v4-flash-free`) ocasionalmente atingem o timeout em requisições longas de geração de código Go/Rust.
- **Solução**:
  1. **Tentativas com Retentativa Exponencial**: 2 tentativas automáticas com aumento progressivo do tempo limite (`httpx.Timeout`).
  2. **Fallback Transparente**: Em caso de falha persistente no endpoint/modelo primário (incluindo OmniRoute customizado), a chamada faz fallback automático para modelos secundários ou para o `OpenCodeRunner`.

---

## 🛠️ 2. Resumo das Implementações da Sessão

| Componente | Módulo | Descrição / Solução |
|---|---|---|
| **Multi-Stack Gate** | `developer.py` | AST/Compilador roda `cargo check` (Rust), `go vet ./...` (Go), `node --check` (JS/TS) e `ast.parse` (Python). |
| **Self-Healing QA** | `qa.py` | Resolução automática de `requires rustc / edition2024` no `Cargo.toml` e `npm install --legacy-peer-deps`. |
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
