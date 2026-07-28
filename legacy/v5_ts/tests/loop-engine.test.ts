import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { LoopEngine } from "../src/core/loop-engine.js";
import type { LoopForgeConfig } from "../src/config/schema.js";
import { MemoryManager } from "../src/memory/manager.js";

describe("LoopForge Engine Integration", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-engine-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve executar o loop e encerrar com sucesso quando o harness passa", async () => {
    const config: LoopForgeConfig = {
      projectName: "Test Engine",
      version: "3.0.0",
      harness: {
        runners: [
          { name: "Pass Runner", type: "unit", command: "echo 'All tests passed'", timeoutMs: 5000, enabled: true },
        ],
      },
      guardrails: {
        maxTotalIterations: 5,
        maxConsecutiveFailures: 3,
        maxBudgetUsd: 5.0,
      },
      memory: {
        lessonsFile: path.join(tmpDir, "lessons.md"),
        handoffFile: path.join(tmpDir, "handoff.md"),
      },
    };

    const engine = new LoopEngine(config, tmpDir);

    const result = await engine.runLoop(async (prompt, iter) => {
      expect(prompt).toContain("LoopForge Iteração #1");
      return `Agente respondeu no passo ${iter}`;
    });

    expect(result.success).toBe(true);
    expect(result.totalIterations).toBe(1);
    expect(result.stopReason).toContain("SUCESSO");
  });

  it("deve acionar o Circuit Breaker e registrar lição aprendida em falhas consecutivas", async () => {
    const lessonsFile = path.join(tmpDir, "lessons.md");

    const config: LoopForgeConfig = {
      projectName: "Failing Engine",
      version: "3.0.0",
      harness: {
        runners: [
          {
            name: "Failing Runner",
            type: "unit",
            command: "node -e 'process.exit(1);'",
            timeoutMs: 5000,
            enabled: true,
          },
        ],
      },
      guardrails: {
        maxTotalIterations: 10,
        maxConsecutiveFailures: 2,
        maxBudgetUsd: 5.0,
      },
      memory: {
        lessonsFile,
        handoffFile: path.join(tmpDir, "handoff.md"),
      },
    };

    const engine = new LoopEngine(config, tmpDir);

    const result = await engine.runLoop(async () => {
      return "Tentando corrigir o erro...";
    });

    expect(result.success).toBe(false);
    expect(result.totalIterations).toBe(2);
    expect(result.stopReason).toContain("Circuit Breaker ATIVADO");

    const memoryManager = new MemoryManager(config.memory, tmpDir);
    const lessonsContent = await memoryManager.readLessonsPrompt();
    expect(lessonsContent).toContain("Failing Runner");
  });
});
