# 🚀 LoopForge v6

**Autonomous Agent Governance and Pipeline Orchestrator**

LoopForge é um motor autônomo de *Loop Engineering* e orquestrador de governança para agentes de IA. Construído em Python 3.12+ com **LangGraph**, **Pydantic v2** e ontologia do **The Foundry**, ele gerencia o ciclo de desenvolvimento autônomo com resiliência industrial, guardrails orçamentários, roteamento adaptativo e telemetria SQLite.

> **Versão Atual:** 6.0.0  
> **Arquitetura Base:** Python + LangGraph (`StateGraph`)  
> **Provedores de LLM:** OpenRouter (`inclusionai/ling-3.0-flash:free`), Google GenAI (Gemini), OpenCode  
> **License:** MIT  

---

## 🌟 Principais Funcionalidades da v6

| Módulo | Descrição | Status |
|---|---|---|
| **LangGraph Pipeline** | Stateful Graph com papéis de **CPO**, **PM**, **Tech Lead**, **Developer** e **QA** | ✅ |
| **Roteamento Adaptativo** | Suporte a **Full-Path** (hierarquia completa) e **Fast-Path** (Dev → QA direto) | ✅ |
| **Spec Review Gate** | Gate interativo em CLI (`lf plan`) para aprovação e edição de especificações | ✅ |
| **Integração OpenRouter** | Chamada direta ao modelo **Ling 3.0 Flash Free** com parsing de JSON resiliente | ✅ |
| **Guardrails & Circuit Breaker** | Limite orçamentário (USD), controle de falhas e travamento via `loop.lock` | ✅ |
| **Security Scanner** | Auditoria de código em busca de secrets e funções perigosas com opção `--fix` | ✅ |
| **Telemetria SQLite & Checkpointing** | Persistência de sessões, histórico de requisições LLM e suporte a `run --replay` | ✅ |

---

## 💻 Instalação

### Pré-requisitos
- **Python** >= 3.12
- **uv** ou **pip**

```bash
# Clone o repositório
git clone https://github.com/Lucas-Damasceno-dev/LoopForge.git
cd LoopForge

# Instalar dependências e CLI em modo editável com uv
uv pip install -e .

# Ou via pip padrão
pip install -e .
```

---

## ⚡ Quick Start

```bash
# 1. Inicializar configuração no repositório atual
lf init

# 2. Criar e revisar uma especificação de projeto (Spec Review Gate)
lf plan --vision "Criar um módulo Python de utilitários matemáticos" --mode full

# 3. Executar o ciclo do pipeline agentico
lf run

# 4. Executar uma tarefa rápida em Fast-Path (direto Dev -> QA)
lf plan --vision "Corrigir cálculo de desconto" --mode fast
lf run

# 5. Auditar segurança do código gerado
lf audit . --fix

# 6. Exibir o status das tarefas e telemetria
lf status
```

---

## 📋 Referência da CLI (`lf` / `loopforge`)

| Comando | Descrição |
|---|---|
| `lf init [dir]` | Inicializa a configuração `.loopforge.json` e ambiente do projeto |
| `lf plan` | Gera plano de tarefas com Spec Review Gate interativo (`--mode full\|fast`) |
| `lf run` | Executa o pipeline de agentes (`--mock`, `-i/--interactive`, `--replay <session>`) |
| `lf status` | Exibe o painel de status do plano, tarefas e telemetria das sessões |
| `lf audit [dir]` | Executa o scanner de segurança em busca de vulnerabilidades e secrets (`--fix`) |
| `lf generate-tests` | Gera suítes de teste unitário baseline para módulos do projeto |
| `lf release [version]` | Gera notas de lançamento semânticas e atualiza o `CHANGELOG.md` |

---

## ⚙️ Configuração (`.loopforge.json`)

Exemplo de arquivo de configuração `.loopforge.json`:

```json
{
  "project_id": "meu-projeto",
  "vision": "Aplicação autônoma gerenciada por agentes de IA",
  "stack": "python",
  "budget_limit_usd": 10.0,
  "max_retries_per_task": 3,
  "llm_provider": "openrouter",
  "llm_model": "inclusionai/ling-3.0-flash:free",
  "plan": {
    "tasks": [
      {
        "id": "T-001",
        "title": "Executar developer: Módulo principal",
        "persona": "developer",
        "routing_mode": "fast",
        "status": "pending"
      }
    ]
  }
}
```

---

## 🧪 Testes

```bash
# Executar a suíte de testes completa do Python v6
uv run pytest
```

- **36/36 testes aprovados** em `tests_py/`
- Cobertura completa de Roteamento Adaptativo, LangGraph, OpenRouter Ling 3.0 Flash Free, Security Scanner e Telemetria SQLite.
