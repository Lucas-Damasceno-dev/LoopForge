import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { AgentExecutor } from "../src/core/agent-executor.js";
import { LLMEngine } from "../src/llm/provider.js";

describe("LoopForge Agent Executor", () => {
  let tempDir: string;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-executor-test-"));
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("deve executar um ciclo de agente aplicando alterações no disco se ferramentas forem chamadas", async () => {
    const executor = new AgentExecutor(tempDir);
    const mockLlm = new LLMEngine({ provider: "opencode" });

    // Mock generateStep para emitir chamada de ferramenta
    mockLlm.generateStep = async () => ({
      content: `
Vou ajustar o código conforme solicitado.
<tool_call>
{
  "name": "write_file",
  "args": {
    "path": "fix.txt",
    "content": "Fixed code content"
  }
}
</tool_call>
`,
      modelUsed: "mock-model",
      isFallback: false,
      tokensUsed: 100,
      estimatedCostUsd: 0.0,
    });

    const result = await executor.executeAgentStep("Prompt de teste", mockLlm);
    expect(result.filesModified).toBe(true);
    expect(result.toolResults).toHaveLength(1);
    expect(result.toolResults[0].success).toBe(true);

    const contentOnDisk = await fs.readFile(path.join(tempDir, "fix.txt"), "utf-8");
    expect(contentOnDisk).toBe("Fixed code content");
  });

  it("deve enriquecer o prompt com instruções de ferramenta e RAG", async () => {
    const executor = new AgentExecutor(tempDir);
    const prompt = await executor.buildEnhancedPrompt("Instrução base", "Erro no teste Unit Tests");
    expect(prompt).toContain("INSTRUÇÕES DE EXECUÇÃO DE FERRAMENTAS");
    expect(prompt).toContain("Instrução base");
  });
});
