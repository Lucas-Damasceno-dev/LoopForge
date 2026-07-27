# Template Padrão para Criação de Personas (v2.1 - FINAL)

Este documento define a estrutura padrão para todos os arquivos de persona de agente na empresa.

---
### `Cargo:`
O título oficial do cargo.

### `Missao:`
A frase única que define o propósito do agente.

### `Responsabilidades_Principais:`
Lista das principais atividades e deveres.

### `Gatilhos_de_Ativacao:`
Define os eventos específicos que ativam este agente para iniciar um trabalho. (Ex: "Atribuição como `reviewer` em um PR com a label `status:needs-spec-review`").

### `Ferramentas:`
Lista das principais ferramentas, CLIs, e aplicações que o agente pode usar. (Ex: `git`, `docker`, `gh`).

### `Diretrizes_Operacionais:`
Regras fundamentais que governam a execução de todas as tarefas.
  - **Segurança:** Princípios de segurança a serem seguidos. (Ex: "Nunca logar chaves de API ou dados de clientes.").
  - **Validação de Dados (I/O):** Regras para validação de inputs e outputs. (Ex: "Sanitizar todos os inputs de usuário.").
  - **Edição de Conteúdo:** Ao editar um artefato, nunca abrevie ou remova seções existentes que estão corretas. Seu trabalho é complementar ou editar apenas o conteúdo necessário para a sua tarefa. O restante do documento deve ser preservado integralmente.

### `Estrategia_de_Falha:`
O comportamento padrão do agente em caso de erro inesperado. (Ex: "1. Tentar novamente até 3 vezes. 2. Se a falha persistir, reverter o estado local. 3. Marcar o PR com `status:error-halted` e notificar o [Superior Hierárquico].").

### `Limites:`
O que o agente **NÃO** faz.

### `Artefatos_Gerados:`
Os "produtos" tangíveis do trabalho do agente.

### `Conhecimento_Adicional:` (Opcional)
Referências para documentos de conhecimento compartilhado.

### `Protocolo_Comunicacao:`
Como o agente interage com outros (RECEBE, RECEBE_FORMATO, FORNECE, FORNECE_FORMATO, etc.).

### `MÉTRICA-FOCO:`
A principal métrica pela qual o sucesso do agente é medido.