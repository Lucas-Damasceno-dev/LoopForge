# Auditoria do Projeto: Definições de Artefatos Pendentes

Esta é uma lista de artefatos que são mencionados nas personas dos agentes, mas que ainda não possuem um schema ou template formal definido em `company_context/shared_knowledge/artifact_templates/`.

## Prioridade Alta

-   **`bug_report.json`**:
    -   **Mencionado por:** QA (gera), Desenvolvedor (recebe), PM (recebe).
    -   **Status:** **CONCLUÍDO**. Os arquivos `bug_report_schema.json` e `bug_report_example.json` foram criados.

## Prioridade Média (Artefatos do Fluxo Principal)

-   **`tech_spec.md`**:
    -   **Mencionado por:** Arquiteto (gera), Desenvolvedor (recebe), AppSec (recebe).
    -   **Status:** Não possui um schema/template formal.

### **(NOVO)** Requisitos do Arquiteto para DevOps

-   **`deployment_requirements.json`**:
    -   **Mencionado por:** Arquiteto (gera), DevOps (recebe).
    -   **Status:** **CONCLUÍDO**.
-   **`rollback_requirements.json`**:
    -   **Mencionado por:** Arquiteto (gera), DevOps (recebe).
    -   **Status:** **CONCLUÍDO**.
-   **`infrastructure_requirements.json`**:
    -   **Mencionado por:** Arquiteto (gera), DevOps (recebe).
    -   **Status:** Novo. Precisa de schema e exemplo.
-   **`data_migration_requirements.json`**:
    -   **Mencionado por:** Arquiteto (gera), DevOps (recebe).
    -   **Status:** Novo. Precisa de schema e exemplo.

### Outros Artefatos do Fluxo

-   **`release_notes.md`**:
    -   **Mencionado por:** PM (gera).
    -   **Status:** Não possui um template.

-   **`vulnerability_report.json`**:
    -   **Mencionado por:** AppSec (gera).
    -   **Status:** **CONCLUÍDO**.

-   **`postmortem-request.md`**:
    -   **Mencionado por:** AppSec (gera).
    -   **Status:** Não possui um schema/template.

-   **`test_execution_report.json`**:
    -   **Mencionado por:** QA (gera).
    -   **Status:** **CONCLUÍDO**.

## Prioridade Baixa (Documentos Estratégicos e Secundários)

-   **`epic-draft.md`**:
    -   **Mencionado por:** CPO (gera).
    -   **Status:** Definido como "linguagem natural", mas um template para guiar as seções seria útil.

-   **"Documento de Visão e Estratégia de Produto" / "Roadmap de Produto"**:
    -   **Mencionado por:** CPO, PM.
    -   **Status:** Não possuem templates.

-   **`architectural_report.md`**:
    -   **Mencionado por:** Arquiteto (gera).
    -   **Status:** Não possui um template.

-   **`user_research_report.md` / `prototype_feedback.md`**:
    -   **Mencionado por:** PM (recebe do UX/UI).
    -   **Status:** Não possuem schemas/templates (a serem definidos com a persona de UX/UI).
