# Memorandum de Contexto e Lições Aprendidas — LoopForge & Git-Pet (v6)

## 📌 Visão Geral da Sessão
Este documento consolida todas as investigações, correções de bugs, configurações de ambiente e aprendizados adquiridos durante a sessão de desenvolvimento do **Git Tamagotchi (`git-pet`)** em Rust utilizando o **LoopForge** integrado ao **OmniRoute**.

---

## 🛠️ 1. Configuração de Ambiente & Python `.venv`

### Problemas Encontrados & Soluções:
- ** PEP 668 (`externally-managed-environment`)**: O Python 3.12 no Linux bloqueia `pip install` global no sistema.
- **Mudança de caminho do projeto**: Ao mover/renomear o repositório pai (ex: adicionando a pasta `agentes/`), os caminhos absolutos internos do `.venv` ficaram quebrados (`VIRTUAL_ENV` mismatch).
- **Módulo `lf` não encontrado**: Faltava a seção `[project.scripts]` no `pyproject.toml`.

### Como recriar/manter o ambiente 100% funcional:
```bash
# Na raiz do LoopForge:
rm -rf .venv
uv venv
uv pip install -e .
uv pip install -e packages/genome -e packages/registry -e packages/retro
source .venv/bin/activate
```

---

## 🔌 2. Integração LLM via OmniRoute & OpenCode Zen

### Configurações de Conexão:
O **OmniRoute** está rodando localmente na porta `http://localhost:20128/v1`.

Variáveis de ambiente definitivas:
```bash
export OPENROUTER_BASE_URL="http://localhost:20128/v1"
export OPENROUTER_API_KEY="sk-omniroute-local"
export OPENROUTER_MODEL="oc/deepseek-v4-flash-free"
export OPENCODE_MODEL="oc/deepseek-v4-flash-free"
```

### Aprendizados & Fixes Aplicados no Código do LoopForge:
1. **Modelo Recomendado**: `oc/deepseek-v4-flash-free` (DeepSeek V4 Flash Free do OpenCode Zen). Apresenta latência de **8ms**, custo **$0.00**, alta capacidade de raciocínio e geração de código Rust limpo.
2. **Suporte a SSE / Streaming (`src/lf/pipeline/llm_factory.py`)**:
   - Ajustado `call_openrouter_api` para enviar `"stream": False` e adicionar um parser genérico paraServer-Sent Events (`data: {"choices": ...}`), evitando erros `Expecting value: line 1 column 1`.
3. **Timeout de HTTP Ajustável (`src/lf/pipeline/llm_factory.py`)**:
   - Aumentado timeout de chamadas HTTP de 30s para **180s** (`OPENROUTER_TIMEOUT`) para evitar cancelamentos precoces enquanto LLMs geram tokens de raciocínio.
4. **Instanciação Flexível de Schemas (`src/lf/runner/opencode/llm.py`)**:
   - Suporte adicionado para quando a LLM retorna listas em vez de dicionários para instanciar Pydantic models.

---

## 🏗️ 3. Arquitetura do Grafo & Fluxo dos Agentes

### Sequência do Pipeline (Modo Full):
`CPO` ➔ `PM` ➔ `Tech Lead` ➔ `Developer` ➔ `QA` ➔ `Parallel Audit` (`AppSec` + `DevOps` paralelos) ➔ `Lessons`

### Regra do Grafo no Nó QA (`should_retry` em `src/lf/pipeline/graph.py`):
- **`tests_failed == 0`**: Avança **imediatamente** para a auditoria paralela `parallel_audit` (`AppSec` + `DevOps` executados simultaneamente via `ThreadPoolExecutor`).
- **`tests_failed > 0` e `qa_attempt < max_retries (3)`**: Retorna ao `developer` com relatório de erros para correção.
- **Tentativas esgotadas (3/3)**: Interrompe no QA.

### Fix Aplicado no Nó QA (`src/lf/pipeline/nodes/qa.py`):
- `_run_harness` agora converte a `@dataclass` `TestHarnessResult` para dicionário usando `dataclasses.asdict()`, prevenindo o erro `AttributeError: 'TestHarnessResult' object has no attribute 'get'`.

---

## 🦀 4. Especificações do Projeto `git-pet` (Rust CLI)

### Localização:
`examples/git-pet/`

### Compatibilidade Cargo / Rust (Edição 2021 vs 2024):
- **Cargo 1.75.0**: Não suporta a futura edição instável `edition2024`.
- **Fix no `Cargo.toml`**: Dependências foram fixadas para edições compatíveis com Rust 2021 (`clap = "=4.4.18"`, `serde = "1.0"`, `anyhow = "1.0"`, `colored = "2.0"`).

### Módulos Gerados:
- `src/main.rs`: CLI Clap (comandos `init`, `status`, `feed`, `stats`, `commit-event`, `setup`).
- `src/pet.rs`: Lógica de XP, Fome (0-100), Humor (`happy`, `sad`, `sick`) e Evolução (`Egg` ➔ `Elder`).
- `src/ascii_art.rs`: Sprites ASCII coloridos por espécie (`Cat`, `Dog`, `Dragon`, `Fox`, `Whale`) e humor.
- `tests/integration_test.rs`: Suíte de testes de integração.

---

## 🚀 Guia Rápido para Próximas Sessões

Para retomar o desenvolvimento ou gerar novos exemplos em sessões futuras:

```bash
# 1. Ativar ambiente virtual
source .venv/bin/activate

# 2. Exportar variáveis do OmniRoute com DeepSeek V4 Flash Free
export OPENROUTER_BASE_URL="http://localhost:20128/v1"
export OPENROUTER_API_KEY="sk-omniroute-local"
export OPENROUTER_MODEL="oc/deepseek-v4-flash-free"
export OPENCODE_MODEL="oc/deepseek-v4-flash-free"

# 3. Executar LoopForge em um diretório de exemplo
cd examples/git-pet
lf run --idea "Sua ideia aqui..." --stack rust
```
