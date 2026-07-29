# 🚀 LoopForge v6

**Autonomous Agent Governance and Pipeline Orchestrator**

LoopForge é um motor autônomo de *Loop Engineering* e orquestrador de governança para agentes de IA. Construído em Python 3.12+ com **LangGraph**, **Pydantic v2**, **FastAPI**, **WebSockets** e a ontologia do **The Foundry**, ele gerencia o ciclo de desenvolvimento autônomo de software com resiliência industrial, auditoria paralela (AppSec + DevOps), governança de orçamento e pontuação ELO de benchmarks.

> **Versão Atual:** 6.0.0  
> **Arquitetura Base:** Python + LangGraph (`StateGraph`)  
> **Provedores de LLM:** OpenRouter (`inclusionai/ling-3.0-flash:free`), Google GenAI (Gemini), OpenCode  
> **License:** MIT  

---

## 🌟 Exemplos Reais Gerados pelo LoopForge

Abaixo está a galeria de projetos reais **100% gerados autonomamente** pela pipeline de agentes do LoopForge, incluindo código principal, manifestos de dependência, suítes de testes unitários e o relatório `lessons.md`:

| Projeto | Stack Tecnológica | Arquivos Gerados | Compila & Testa? | Status QA | Link da Galeria |
|---|---|---|---|---|---|
| **Java Spring Boot Task API** | Java 17 + Maven | `pom.xml`, `TaskApiApplication.java`, `TaskApiApplicationTest.java`, `lessons.md` | ✅ `mvn test` | **PASS (100%)** | [Ver Exemplo](examples/gallery/java_spring_boot_task_api) |
| **Rust CLI Dollar Quote** | Rust + Cargo | `Cargo.toml`, `src/main.rs`, `tests/test_main.rs`, `lessons.md` | ✅ `cargo test` | **PASS (100%)** | [Ver Exemplo](examples/gallery/rust_dollar_quote_cli) |
| **Python FastAPI HTMX Dashboard** | Python + FastAPI + HTMX | `pyproject.toml`, `main.py`, `tests/test_main.py`, `lessons.md` | ✅ `pytest` | **PASS (100%)** | [Ver Exemplo](examples/gallery/python_fastapi_htmx_dashboard) |

---

## ⚡ Funcionalidades do Ecossistema v6

| Módulo | Descrição | Status |
|---|---|---|
| **LangGraph Multi-Agent DAG** | Papéis autônomos de **CPO**, **PM**, **Tech Lead**, **Developer**, **QA**, **AppSec** e **DevOps** | ✅ |
| **Stack Decidida pelo Tech Lead** | O Tech Lead avalia a ideia e define a melhor stack (`rust`, `java`, `python`, `go`, `js`) sem engessar a CLI | ✅ |
| **Auditoria Simultânea Paralela** | Execução concorrente de **AppSec** (Security Review) e **DevOps** (CI/CD) via ThreadPoolExecutor | ✅ |
| **Benchmark ELO System** | Suíte de 10 problemas curados para medição quantitativa da qualidade e rating ELO (`lf benchmark`) | ✅ |
| **FastAPI REST & WebSockets UI** | Painel Web interativo ao vivo em tempo real com recepção de logs e HITL | ✅ |
| **GitHub Action & `lf pr`** | Integração contínua para CI/CD (`action.yml`) e criação autônoma de Pull Requests (`lf pr`) | ✅ |
| **Otimização de Custos LLM** | Cache semântico SQLite e compressão inteligente de prompts no `llm_factory` | ✅ |

---

## 💻 Instalação

### Pré-requisitos
- **Python** >= 3.12
- **pip** ou **uv**

```bash
# Clone o repositório
git clone https://github.com/Lucas-Damasceno-dev/LoopForge.git
cd LoopForge

# Instalar dependências e a CLI LoopForge em modo editável
pip install -e .
```

---

## ⚡ Quick Start

```bash
# 1. Executar a pipeline autônoma para criar um projeto (Tech Lead decide a stack)
lf run --idea "CLI em Rust que lê CSV e calcula estatísticas"

# 2. Forçar uma stack específica via override de usuário
lf run --idea "API REST de Tarefas" --stack java

# 3. Executar em segundo plano e abrir Pull Request no GitHub ao concluir
lf run --idea "Dashboard financeiro em Python" --pr

# 4. Iniciar o Servidor REST API & Web Dashboard UI ao vivo
lf serve --port 8000

# 5. Medir o ELO Rating do pipeline contra a suíte de benchmarks curados
lf benchmark

# 6. Criar commit e Pull Request em qualquer diretório de projeto gerado
lf pr --dir ./meu-projeto --idea "Feature de Autenticação"
```

---

## 📋 Referência da CLI (`lf` / `loopforge`)

| Comando | Descrição |
|---|---|
| `lf run` | Executa o pipeline autônomo dos agentes (`--idea`, `--stack`, `--pr`, `--mock`, `-i`) |
| `lf serve` | Inicia o servidor REST API e a Web Dashboard UI ao vivo com WebSockets |
| `lf benchmark` | Executa a suíte de benchmarks curados e reporta a pontuação ELO do pipeline |
| `lf resume` | Retoma execuções de pipeline pausadas a partir de checkpoints no LangGraph |
| `lf diff` | Exibe diferenças de código entre retentativas e gerações |
| `lf explore` | Explorador interativo de artefatos, especificações e relatórios de teste |
| `lf pr` | Inicializa repositório Git, commita alterações e abre Pull Request no GitHub |

---

## 🧪 Testes Automatizados

```bash
# Executar a suíte de testes unitários e de integração
.venv/bin/pytest tests_py
```

- **122 testes aprovados** em `tests_py/`
- Cobertura completa de Decisão Autônoma de Stack pelo Tech Lead, Auditoria Paralela AppSec+DevOps, WebSockets Live, ELO Rating e Gerador `lessons.md`.
