# Pré-requisitos do Ecossistema de Agentes

Este arquivo lista as dependências de linha de comando (CLIs) e outras ferramentas de software que precisam estar instaladas no ambiente para que os agentes funcionem corretamente.

## Ferramentas Fundamentais (Usadas por Quase Todos)

- **`git`:**
  - **Agentes:** Todos
  - **Uso:** Controle de versão, base do workflow Git-nativo.
  - **Link:** [https://git-scm.com/book/en/v2/Getting-Started-Installing-Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

- **`gh` (GitHub CLI):**
  - **Agentes:** PM, Arquiteto, CPO, Desenvolvedor, QA, AppSec, DevOps
  - **Uso:** Automação de tarefas no GitHub (PRs, issues, labels).
  - **Link:** [https://github.com/cli/cli#installation](https://github.com/cli/cli#installation)

- **`docker`:**
  - **Agentes:** Desenvolvedor, DevOps
  - **Uso:** Construção de imagens de aplicação e execução de ambientes locais.
  - **Link:** [https://docs.docker.com/engine/install/](https://docs.docker.com/engine/install/)

## Ferramentas de DevOps e Infraestrutura

- **`terraform`:**
  - **Agente:** DevOps
  - **Uso:** Gerenciamento de Infraestrutura como Código (IaC).
  - **Link:** [https://learn.hashicorp.com/tutorials/terraform/install-cli](https://learn.hashicorp.com/tutorials/terraform/install-cli)

- **`kubectl`:**
  - **Agente:** DevOps
  - **Uso:** Interação com clusters Kubernetes para depuração e gerenciamento.
  - **Link:** [https://kubernetes.io/docs/tasks/tools/](https://kubernetes.io/docs/tasks/tools/)

- **`helm`:**
  - **Agente:** DevOps
  - **Uso:** Gerenciamento de pacotes de aplicação no Kubernetes.
  - **Link:** [https://helm.sh/docs/intro/install/](https://helm.sh/docs/intro/install/)

- **Agentes GitOps (Conceitual):**
  - **Agente:** DevOps (colabora com)
  - **Ferramentas:** `ArgoCD`, `FluxCD`
  - **Uso:** Sincronização contínua entre o repositório de estado e o cluster. Não são CLIs que o agente DevOps executa diretamente, mas ele gerencia suas configurações.

## Ferramentas de Segurança (AppSec)

- **Análise de Dependências (SCA):** `Snyk CLI`, `Trivy`, `Grype`
- **Análise Estática (SAST):** `SonarQube` (via API/CLI)
- **Análise Dinâmica (DAST):** `OWASP ZAP` (via API)

## Ferramentas de Teste (QA)

- **Frameworks de Teste:** `JUnit`, `Pytest`, `Go Test`, `Cypress`, `Playwright`, `Pact CLI`
- **Teste de API:** `Postman CLI` (Newman), `curl`

## Ferramentas de Desenvolvimento e Arquitetura

- **Ferramentas de Build:** `mvn`, `gradle`, `npm`, `go build`
- **Diagramação:** `mermaid` / `plantuml` CLI
- **Scaffolding:** `cookiecutter`

---
*Nota: Muitas das ferramentas de teste, build e segurança são específicas da linguagem/stack e seriam instaladas como parte do ambiente do projeto, não necessariamente como pré-requisitos globais do sistema.*