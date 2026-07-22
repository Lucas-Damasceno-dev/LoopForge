import { SWARM_ROLES, type AgentRoleType } from "./roles.js";
import type { LLMEngine, LLMResponse } from "../llm/provider.js";

export interface SwarmStepResult {
  role: AgentRoleType;
  roleName: string;
  response: string;
  modelUsed: string;
  isFallback: boolean;
}

export interface SwarmExecutionResult {
  steps: SwarmStepResult[];
  finalHandoff: string;
}

export class SwarmOrchestrator {
  constructor(private llmEngine: LLMEngine) {}

  public async executeSwarmPipeline(
    promptContext: string,
    consecutiveFailures: number,
    cwd: string = "."
  ): Promise<SwarmExecutionResult> {
    const rolesOrder: AgentRoleType[] = ["architect", "coder", "tester", "reviewer"];
    const steps: SwarmStepResult[] = [];
    let intermediateContext = promptContext;

    for (const roleType of rolesOrder) {
      const roleDef = SWARM_ROLES[roleType];

      const rolePrompt = `${roleDef.systemPrompt}\n\n${intermediateContext}`;

      const llmRes: LLMResponse = await this.llmEngine.generateStep(rolePrompt, consecutiveFailures, cwd);

      steps.push({
        role: roleType,
        roleName: roleDef.name,
        response: llmRes.content,
        modelUsed: llmRes.modelUsed,
        isFallback: llmRes.isFallback,
      });

      intermediateContext += `\n\n### 🤝 Swarm Transition (${roleDef.name}):\n${llmRes.content.slice(0, 300)}...`;
    }

    const finalHandoff = steps.map((s) => `**[${s.roleName}]**: ${s.response.slice(0, 150)}...`).join("\n");

    return {
      steps,
      finalHandoff,
    };
  }
}
