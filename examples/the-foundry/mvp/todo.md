# TODO - MVP LangGraph (Revisado)

Esta lista de tarefas é focada na construção de um MVP (Minimum Viable Product) usando LangGraph para o

---

## Fase 1: Estrutura e Esqueleto do Grafo (CONCLUÍDA)
- [x] 1. Configurar o ambiente do projeto MVP.
- [x] 2. Definir a estrutura do grafo em `mvp/src/main.py`.
- [x] 3. Montar e Compilar o Grafo em `mvp/src/main.py`.

---

## Fase 2: Implementação da Lógica dos Agentes & Refatoração (CONCLUÍDA & Melhorada)
- [x] 4. Implementar a lógica dos nós (agentes): CPO, Product Manager, Tech Lead, Developer, QA.
- [x] 5. Refatorar código dos estados: externalizar dados mock e templates para arquivos dedicados.
- [x] 6. Implementar Factory para Clientes LLM: centralizar a criação de clientes LLM (Google Gemini, Ollama, OpenRouter).
- [x] 7. Corrigir e verificar fluxos e transições de agentes em modo mock.

---

## Fase 3: Levantamento e Planejamento (CPO, Product Manager, Tech Lead)

- [ ] 8. **Implementar Feedback Loop PM-TL com Interação do Usuário:**
    - [ ] 8.1. **Expandir `GraphState`:** Adicionar campos `user_question`, `user_response`, `needs_user_input` para gerenciar a interação com o usuário.
    - [ ] 8.2. **Criar Nó "User Input":** Desenvolver um nó `user_input` que lida com a pausa do grafo, solicitação de entrada ao usuário e atualização do `GraphState`.
    - [ ] 8.3. **Refinar Lógica do Product Manager:** Adicionar capacidade para o PM interpretar o feedback do Tech Lead (`pm_feedback`), tentar responder internamente e, se necessário, formular `user_question` para o usuário.
    - [ ] 8.4. **Refinar Lógica do Tech Lead:** Melhorar o processo de validação de User Stories para gerar feedback mais claro e acionável, com base nos requisitos técnicos.
    - [ ] 8.5. **Ajustar Router:** Modificar o roteador para que, se `needs_user_input=True`, o fluxo vá para o nó 'User Input'; se houver `pm_feedback` (sem `needs_user_input`), o fluxo retorne ao Product Manager; caso contrário, avance para o Desenvolvimento.

- [ ] 9. **Mapeamento Detalhado do Processo de Desenvolvimento:**
    - [ ] 9.1. Definir o ciclo de vida completo de um artefato (épico, user story, tech spec) e as transições de estado.
    - [ ] 9.2. Criar templates mais ricos para o CPO gerar épicos e para o PM gerar User Stories.
    - [ ] 9.3. **Validação de Schemas:** Adicionar passos de validação explícitos para garantir que artefatos gerados (JSON) estejam em conformidade com seus schemas esperados.

---

## Fase 4: Desenvolvimento (Developer, QA)

- [ ] 10. **Refinar Geração de Código pelo Developer:**
    - [ ] 10.1. Aprimorar o prompt do Developer para gerar código mais robusto, com foco em modularidade, testes unitários e cobertura de código.
    - [ ] 10.2. Considerar a geração de stubs de testes junto com o código.

- [ ] 11. **Melhorar Processo de QA:**
    - [ ] 11.1. Aprimorar o prompt do QA para uma análise mais profunda do código, identificando padrões, vulnerabilidades e potenciais melhorias.
    - [ ] 11.2. Integrar análise estática de código (ex: flake8, pylint para Python) na etapa de QA.
    - [ ] 11.3. Introduzir a geração de planos de teste detalhados pelo QA.

---

## Fase 5: Infraestrutura e Persistência

- [ ] 12. **Implementar Persistência de Artefatos em Banco de Dados:**
    - [ ] 12.1. Configurar um banco de dados (ex: SQLite) para armazenar épicos, user stories, tech specs, códigos e relatórios de teste.
    - [ ] 12.2. Atualizar todos os agentes para ler/escrever artefatos do/para o banco de dados, em vez de arquivos locais.
    - [ ] 12.3. Implementar versionamento básico para cada tipo de artefato no DB.

- [ ] 13. **Mecanismos de Resiliência e Monitoramento:**
    - [ ] 13.1. Implementar tratamento de erros mais robusto para chamadas LLM (retries, timeouts, fallback strategies).
    - [ ] 13.2. Adicionar logging estruturado para a execução do grafo e os nós dos agentes.

---

## Fase 6: Deploy (Futuro)
- [ ] 14. **Definir Arquitetura de Deploy:**
    - [ ] 14.1. Criar um agente DevOps para orquestrar o deploy e gerenciamento de infraestrutura.
    - [ ] 14.2. Definir a estratégia de deploy (CI/CD).
