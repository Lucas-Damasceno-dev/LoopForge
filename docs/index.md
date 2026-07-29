# LoopForge v6

> **Autonomous Agent Governance and Pipeline Orchestrator**

LoopForge é um motor autônomo de *Loop Engineering* e orquestrador de governança para agentes de IA de nível empresarial. Construído em Python 3.12+ com **LangGraph**, **Pydantic v2**, **FastAPI**, **WebSockets** e a ontologia do **The Foundry**, ele gerencia o ciclo de desenvolvimento autônomo de software com resiliência industrial, auditoria paralela, governança de orçamento e pontuação ELO.

---

## 🌟 Principais Funcionalidades

- **Pipeline Autônomo de 7 Agentes**: Ciclo completo de governança (`CPO` $\rightarrow$ `PM` $\rightarrow$ `Tech Lead` $\rightarrow$ `Developer` $\rightarrow$ `QA` $\rightarrow$ `AppSec` + `DevOps` em paralelo).
- **Stack Decidida pelo Tech Lead**: O Tech Lead analisa a ideia do projeto e decide a melhor stack (`rust`, `java`, `python`, `go`, `javascript`) sem engessamento da CLI.
- **Geração Multi-Arquivo Autônoma**: O nó Developer gera o manifesto de dependências, código-fonte e suíte de testes organizados em arquivos independentes.
- **Harness de QA com Detecção Automática**: Reconhecimento automático de manifestos e executores de teste (`pom.xml`, `build.gradle`, `Cargo.toml`, `go.mod`, `package.json`, `*.csproj`, `Gemfile`, `pytest`).
- **Auditoria Simultânea Paralela (AppSec + DevOps)**: Execução paralela de análise de segurança e audit de deployability via `ThreadPoolExecutor`.
- **Relatório Final `lessons.md`**: Gerado autonomamente ao fim de cada ciclo com decisões do Tech Lead, contagem de testes, avisos do AppSec e comandos para executar.
- **REST API & WebSockets UI**: Painel Web moderno interativo com transmissão de eventos dos nós em tempo real.
- **Integração GitHub Action & `lf pr`**: Ação reutilizável de CI/CD (`action.yml`) e automação de commit/Pull Request no GitHub (`lf pr` / `run --pr`).
- **Sistema de Benchmark & ELO Rating**: Avaliação de 10 problemas curados multi-stack com histórico de rating ELO (`lf benchmark`).
