import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { LoopEngine } from "../src/core/loop-engine.js";
import type { LoopForgeConfig } from "../src/config/schema.js";
import { readMemoryFile } from "../src/memory/manager.js";

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
      name: "Test Engine",
      version: "1.0.0",
      strategy: "creator",
      skills: { directory: ".loopforge/skills", activeSkills: [] },
      harness: {
        runners: [
          { name: "Pass Runner", type: "unit", command: "echo 'All tests passed'", timeoutMs: 5000 },
        ],
      },
      guardrails: {
        maxIterations: 5,
        maxConsecutiveFailures: 3,
        stopOnSuccess: true,
        allowGitRollback: false,
      },
      memory: {
        lessonsFile: path.join(tmpDir, "lessons.md"),
        handoffFile: path.join(tmpDir, "handoff.md"),
        autoUpdateLessons: true,
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
      name: "Failing Engine",
      version: "1.0.0",
      strategy: "fixed",
      skills: { directory: ".loopforge/skills", activeSkills: [] },
      harness: {
        runners: [
          {
            name: "Failing Runner",
            type: "unit",
            command: "node -e 'process.exit(1);'",
            timeoutMs: 5000,
          },
        ],
      },
      guardrails: {
        maxIterations: 10,
        maxConsecutiveFailures: 2,
        stopOnSuccess: true,
        allowGitRollback: false,
      },
      memory: {
        lessonsFile,
        handoffFile: path.join(tmpDir, "handoff.md"),
        autoUpdateLessons: true,
      },
    };

    const engine = new LoopEngine(config, tmpDir);

    const result = await engine.runLoop(async () => {
      return "Tentando corrigir o erro...";
    });

    expect(result.success).toBe(false);
    expect(result.totalIterations).toBe(2);
    expect(result.stopReason).toContain("CIRCUIT BREAKER DISPARADO");

    const lessonsContent = await readMemoryFile(lessonsFile, "Lições");
    expect(lessonsContent).toContain("Failing Runner");
  });
});
