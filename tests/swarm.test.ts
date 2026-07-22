import { describe, it, expect, vi } from "vitest";
import { SwarmOrchestrator } from "../src/agents/swarm.js";
import type { LLMEngine } from "../src/llm/provider.js";

describe("LoopForge Multi-Agent Swarm", () => {
  it("deve executar a pipeline sequencial dos 4 papéis especialistas (Architect -> Coder -> Tester -> Reviewer)", async () => {
    const mockLLMEngine: LLMEngine = {
      getActiveModel: vi.fn().mockReturnValue({ model: "deepseek-v3", isFallback: false }),
      generateStep: vi.fn().mockImplementation(async (prompt: string) => {
        return {
          content: `Resposta do agente para o prompt: ${prompt.slice(0, 30)}...`,
          modelUsed: "deepseek-v3",
          isFallback: false,
          tokensUsed: 150,
          estimatedCostUsd: 0,
        };
      }),
    } as unknown as LLMEngine;

    const orchestrator = new SwarmOrchestrator(mockLLMEngine);
    const result = await orchestrator.executeSwarmPipeline("Task: Implementar validação de email", 0);

    expect(result.steps.length).toBe(4);
    expect(result.steps[0].role).toBe("architect");
    expect(result.steps[1].role).toBe("coder");
    expect(result.steps[2].role).toBe("tester");
    expect(result.steps[3].role).toBe("reviewer");
    expect(result.finalHandoff).toContain("Architect Agent");
  });
});
