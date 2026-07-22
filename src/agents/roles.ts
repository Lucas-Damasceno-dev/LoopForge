export type AgentRoleType = "architect" | "coder" | "tester" | "reviewer";

export interface AgentRoleDefinition {
  name: string;
  type: AgentRoleType;
  description: string;
  systemPrompt: string;
}

export const SWARM_ROLES: Record<AgentRoleType, AgentRoleDefinition> = {
  architect: {
    name: "Architect Agent",
    type: "architect",
    description: "Analisa requisitos, especifica assinaturas de métodos e projeta a estrutura de arquivos.",
    systemPrompt: `Você é o Agente Arquiteto. Sua função é projetar a estrutura técnica, definir contratos de interface, tipos e listar os arquivos afetados antes da implementação.`,
  },
  coder: {
    name: "Coder Agent",
    type: "coder",
    description: "Implementa o código fonte seguindo o design do Arquiteto e Clean Code.",
    systemPrompt: `Você é o Agente Desenvolvedor. Sua função é implementar o código fonte com alta qualidade, sem remover tratamentos de erro ou quebrar contratos.`,
  },
  tester: {
    name: "Tester Agent",
    type: "tester",
    description: "Cria e atualiza suítes de teste unitários e de integração para cobrir a implementação.",
    systemPrompt: `Você é o Agente de Testes. Sua função é criar testes automatizados rigorosos cobrindo casos de sucesso e borda.`,
  },
  reviewer: {
    name: "Reviewer Agent",
    type: "reviewer",
    description: "Executa o Harness de sensores e audita o código contra as Skills de qualidade ativas.",
    systemPrompt: `Você é o Agente Revisor. Sua função é validar se a implementação atende a todas as Skills ativas e se os testes no Harness estão 100% aprovados.`,
  },
};
