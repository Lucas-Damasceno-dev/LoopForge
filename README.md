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
| **LangGraph Multi-Agent DAG** | 9 nós autônomos: **CPO**, **PM**, **Tech Lead**, **Developer**, **QA**, **AppSec**, **DevOps**, **Parallel Audit**, **Lessons** | ✅ |
| **Stack Decidida pelo Tech Lead** | O Tech Lead avalia a ideia e define a melhor stack (`rust`, `java`, `python`, `go`, `js`) sem engessar a CLI | ✅ |
| **Auditoria Simultânea Paralela** | Execução concorrente de **AppSec** (Security Review) e **DevOps** (CI/CD) via ThreadPoolExecutor | ✅ |
| **Benchmark ELO System** | Suíte de 10 problemas curados para medição quantitativa da qualidade e rating ELO (`lf benchmark`) | ✅ |
| **FastAPI REST & WebSockets UI** | Painel Web interativo ao vivo em tempo real com recepção de logs e HITL | ✅ |
| **GitHub Action & `lf pr`** | Integração contínua para CI/CD (`action.yml`) e criação autônoma de Pull Requests (`lf pr`) | ✅ |
| **Otimização de Custos LLM** | Cache semântico SQLite e compressão inteligente de prompts no `llm_factory` | ✅ |
| **Human-in-the-Loop (HITL)** | Gates interativos nos nós developer, QA e parallel_audit com ações approve/retry/adjust/abort | ✅ |
| **Review Mode** | Pausa antes de salvar artefatos em disco para revisão manual | ✅ |
| **Notificações Desktop & Webhook** | Alertas via notify-send + webhooks Slack/Discord | ✅ |
| **Circuit Breaker** | 3 guardas: falhas consecutivas, iterações máximas, custo máximo USD | ✅ |
| **Memory Manager** | Banco SQLite de lições aprendidas com busca por stack e keywords | ✅ |
| **Security Scanner** | Varredura estática de segurança no nó AppSec | ✅ |
| **Sub-pacotes do Ecossistema** | Codebase Genome, Agentic Interface Registry, Agentic Retro | ✅ |

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
| `lf run` | Executa o pipeline autônomo dos agentes (`--idea`, `--stack`, `--pr`, `--mock`, `-i`, `--review-mode`, `--notify`, `--wizard`, `--webhook-url`) |
| `lf serve` | Inicia o servidor REST API e a Web Dashboard UI ao vivo com WebSockets |
| `lf benchmark` | Executa a suíte de benchmarks curados e reporta a pontuação ELO do pipeline |
| `lf resume` | Retoma execuções de pipeline pausadas a partir de checkpoints no LangGraph |
| `lf diff` | Exibe diferenças de código entre retentativas e gerações |
| `lf explore` | Explorador interativo de artefatos, especificações e relatórios de teste |
| `lf pr` | Inicializa repositório Git, commita alterações e abre Pull Request no GitHub |
| `lf init` | Inicializa um novo projeto LoopForge |
| `lf plan` | Gerencia planos de tarefas do pipeline |
| `lf status` | Exibe o status da execução atual |
| `lf release` | Gera changelog e release notes |
| `lf completion` | Gera script de shell completion (bash/zsh/fish) |
| `lf generate-tests` | Geração automática de testes via agente |
| `lf audit` | Auditoria completa do pipeline |
| `lf export` | Exporta artefatos gerados |
| `lf studio` | Interface web studio interativa |

---

## 🧪 Testes Automatizados

```bash
# Executar a suíte de testes unitários e de integração
pytest tests/
```

- **31 arquivos de teste** em `tests/` (suite ativa)
- **`tests_py/` está depreciado/vazio** — não utilizar
- Cobertura de Decisão Autônoma de Stack, Auditoria Paralela AppSec+DevOps, WebSockets Live, ELO Rating e Lessons Generator
- CI pipeline: `ruff check --select E,F,W,I,N,UP,SIM src/lf tests` → `mypy src/lf` → `pytest --cov=src/lf --cov-fail-under=75 tests/`

---

## 🐳 Docker

```bash
cp .env.example .env
docker compose up -d
```

Acesse `http://localhost:8000/dashboard` para o Dashboard interativo.

---

## 🤖 GitHub Action

LoopForge fornece uma **GitHub Action reutilizável** (`action.yml`) com inputs:

| Input | Descrição |
|---|---|
| `idea` | Ideia/funcionalidade a ser desenvolvida |
| `stack` | Stack tecnológica (opcional) |
| `routing_mode` | full, fast, review-only, explore |
| `openrouter_api_key` | API Key do OpenRouter |
| `mock_llm` | Usar modo mock (boolean) |

---

## 📦 Sub-pacotes do Ecossistema

| Pacote | CLI | Descrição |
|---|---|---|
| **Genome** | `genome` | Codebase Genome — perfil estrutural de codebase (AST, métricas, bus factor) |
| **Registry** | `registry` | Agentic Interface Registry — registro e detecção de quebras de contrato entre agentes |
| **Retro** | `retro` | Agentic Retro — síntese pós-sessão, causas-raiz e recomendações |

---

## 📚 Documentação MkDocs

Documentação completa hospedada via GitHub Pages:

```bash
mkdocs serve    # Preview local
mkdocs build    # Build estático
```
