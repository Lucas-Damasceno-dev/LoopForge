# LoopForge v6

> **Autonomous Agent Governance and Pipeline Orchestrator**

LoopForge é um motor autônomo de *Loop Engineering* e orquestrador de governança para agentes de IA de nível empresarial. Construído em Python 3.11+ com **LangGraph**, **Pydantic v2**, **FastAPI**, **WebSockets** e a ontologia do **The Foundry**, ele gerencia o ciclo de desenvolvimento autônomo de software com resiliência industrial, auditoria paralela, governança de orçamento e pontuação ELO.

---

## 🌟 Principais Funcionalidades

- **Pipeline Autônomo de 9 Agentes**: Ciclo completo de governança (`CPO` $\rightarrow$ `PM` $\rightarrow$ `Tech Lead` $\rightarrow$ `Test Writer` $\rightarrow$ `Developer` $\rightarrow$ `QA` $\rightarrow$ `AppSec` + `DevOps` em paralelo $\rightarrow$ `Lessons`).
- **Stack Decidida pelo Tech Lead**: O Tech Lead analisa a ideia do projeto e decide a melhor stack (`rust`, `java`, `python`, `go`, `javascript`) sem engessamento da CLI.
- **Geração Multi-Arquivo Autônoma**: O nó Developer gera o manifesto de dependências, código-fonte e suíte de testes organizados em arquivos independentes.
- **Harness de QA com Detecção Automática**: Reconhecimento agnóstico de manifestos e executores de teste (`pom.xml`/`mvnw`, `build.gradle`/`gradlew`, `Cargo.toml`, `go.mod`, `package.json`/`vitest.config`, `pyproject.toml` com `[tool.pytest.ini_options]`/`pytest.ini`).
- **Auditoria Simultânea Paralela (AppSec + DevOps)**: Execução paralela de análise de segurança e audit de deployability via `ThreadPoolExecutor`.
- **Routing Adaptativo**: 5 modos de roteamento — `full` (ciclo completo), `fast`/`patch` (Developer→QA→Audit para bugfix), `review-only` (QA→Audit), `explore` (Tech Lead spike).
- **Human-in-the-Loop (HITL)**: Gates interativos nos nós developer, QA e parallel_audit com ações approve/retry/adjust_prompt/adjust_state/continue/pause/abort.
- **Review Mode**: Pausa antes de salvar artefatos em disco para revisão manual.
- **Notificações Desktop & Webhook**: Alertas via notify-send + webhooks Slack/Discord.
- **Circuit Breaker**: 3 guardas (falhas consecutivas, iterações máximas, custo máximo USD) para proteção de budget.
- **Memória Persistente**: Banco SQLite de lições aprendidas com busca por stack e keywords para contexto entre execuções.
- **Security Scanner**: Varredura estática de segurança integrada ao nó AppSec.
- **Relatório Final `lessons.md`**: Gerado autonomamente ao fim de cada ciclo com decisões do Tech Lead, contagem de testes, avisos do AppSec e comandos para executar.
- **REST API & WebSockets UI**: Painel Web moderno interativo com transmissão de eventos dos nós em tempo real.
- **Integração GitHub Action & `lf pr`**: Ação reutilizável de CI/CD (`action.yml`) e automação de commit/Pull Request no GitHub (`lf pr` / `run --pr`).
- **Sistema de Benchmark & ELO Rating**: Avaliação de 10 problemas curados multi-stack com histórico de rating ELO (`lf benchmark`).
- **Sub-pacotes do Ecossistema**: Codebase Genome (perfil estrutural), Agentic Interface Registry (contratos), Agentic Retro (síntese pós-sessão).
- **Docker & Docker Compose**: Imagem multi-stage (`python:3.12-slim`) com healthcheck e dashboard integrado.
