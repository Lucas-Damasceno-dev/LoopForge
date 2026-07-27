# TODO - Próximos Passos do Projeto "Empresa de Agentes"

## 🚀 Projeto e Ecossistema (Geral)

- [x] **1. (Concluído) Definir e Refinar o Workflow:** Detalhar a máquina de estados, o padrão saga e os princípios do ecossistema.
- [ ] **2. Revisar e Finalizar o Template de Persona:** Garantir que o `persona_template.md` (v2.1) está completo.
- [ ] **3. Definir Guias de Conhecimento:**
  - [ ] 3.1. Criar `coding_style.md`.
  - [ ] 3.2. Criar `adr_template.md` e `postmortem_template.md`.
  - [ ] 3.3. **(Novo)** Criar `logging_guidelines.json` para definir o padrão de log da empresa para observabilidade.
- [ ] **4. Validar Personas (Linter):** Criar um script (`validate_personas.py`) para validar a conformidade das personas com o template.
- [ ] **5. Implementar o Carregador de Contexto:** Desenvolver o script (`load_context.py`) que gera o `contexto_estruturado.json`.
- [ ] **6. Prototipar o Primeiro "Slice" com LangGraph:** Criar o protótipo do fluxo "Dupla Dinâmica" (PM -> Arquiteto).
- [ ] **7. Expandir o Grafo:** Adicionar gradualmente mais agentes (Desenvolvedor, QA, etc.) ao grafo do LangGraph.
- [ ] **8. Adicionar a definição do conceito de projeto (Project Schema) que o Tech Lead deve gerar, provendo uma visão macro para o Desenvolvedor.**

## 🤖 Agentes (Personas & Playbooks)

- [ ] **9. Refinar Todas as Personas:** Revisar todos os 11 arquivos `.md` de persona para se alinharem com o template finalizado.
  - [ ] 9.1. Refinar a persona do **CEO**.
  - [ ] 9.2. Refinar a persona do **CFO**.
  - [ ] 9.3. Refinar a persona do **CTO**.
  - [ ] 9.4. Refinar a persona do **UX/UI Designer**.
- [ ] **10. Definir "Playbooks" de Ações:**
  - [ ] 10.1. Playbook de Ciclo de Vida de Artefatos: Mapear qual agente preenche quais campos em cada etapa.
  - [ ] 10.2. Playbook de Geração de Relatórios: Definir como agentes geram relatórios (ex: `release_notes.md`).
  - [ ] 10.3. **(Novo)** Playbook de Análise de Código (SCA/SAST): Definir como agentes usam ferramentas como Snyk/Trivy para checar dependências e SonarQube para análise estática de código.
  - [ ] 10.4. **(Para Avaliar - CPO)** Playbook de Revisão de Roadmap: Definir o processo periódico de análise de roadmap e planejamento estratégico.
  - [ ] 10.5. **(Para Avaliar - CPO)** Playbook de Análise de Oportunidades de Mercado: Definir como o CPO ou PM detecta e formaliza novas oportunidades estratégicas.
  - [ ] 10.6. **(Para Avaliar - AppSec)** Playbook de Análise de Causa Raiz (RCA): Definir o processo para iniciar uma RCA quando uma vulnerabilidade de design 'escapa' para o estágio de revisão de código.
  - [ ] 10.7. **(Para Avaliar - DevOps)** Playbook de Engenharia do Caos: Definir o processo para orquestrar experimentos de Chaos Engineering em ambientes de pré-produção.
  - [ ] 10.8. **(Para Avaliar - PM)** Playbook de Análise de Mercado Periódica: Implementar rotina para análise de mercado e feedback de usuários.
  - [ ] 10.9. **(Para Avaliar - PM)** Playbook de Análise de Concorrentes: Desenvolver capacidade de analisar 'Release Notes' de concorrentes.
  - [ ] 10.10. **(Para Avaliar - PM)** Playbook de Geração de Hipóteses: Integrar com APIs de métricas de produto (ex: Mixpanel) para gerar hipóteses baseadas em dados.
- [ ] **11. (Para Avaliar) Fluxo de Análise de Viabilidade:** Desenhar o workflow para o Arquiteto analisar novas ideias.
- [ ] **12. (Para Avaliar) Investigar Detecção de Loop:** Definir uma estratégia para a detecção de loops infinitos no workflow.
- [ ] **13. Criar Exemplos de Interação (Few-shot):** Desenvolver exemplos de entrada e saída para as interações mais críticas de cada persona, focando na demonstração de comportamento, formato e estilo desejados para o LLM. (Ex: CPO: input do cliente -> epic-draft.md, PM: user_story.json -> tech_spec.md).
- [ ] **14. (WALK) Implementar Lógica de Deploy Avançada (DevOps):** Evoluir o agente DevOps para suportar `rollout_policy` (canary/blue_green) e a validação de `required_secrets`.
- [ ] **15. (RUN) Implementar Lógica de Verificação Ativa (DevOps):** Evoluir o agente DevOps para suportar a seção `verification`, realizando rollbacks automáticos com base em métricas de saúde em tempo real.

## ⚙️ Melhorias de Infraestrutura e Performance

- [ ] **16. Implementar Caching de Respostas LLM:** Utilizar `langchain.cache` (ex: `SQLiteCache`) para cachear as respostas dos modelos e reduzir o consumo da API.
- [ ] **17. Adicionar Banco de Dados para Artefatos:** Integrar um DB (ex: SQLite, PostgreSQL) para persistir e versionar épicos, user stories e outros artefatos gerados.
- [ ] **18. Otimizar Tokens JSON:** Explorar estratégias para comprimir tokens em payloads JSON enviados aos LLMs (ex: chaves abreviadas) e definir um formato otimizado.
