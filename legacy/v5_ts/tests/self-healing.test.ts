import { describe, it, expect } from "vitest";
import { SelfHealingEngine } from "../src/harness/self-healing.js";

describe("LoopForge Self-Healing Engine", () => {
  it("deve detectar se falhas de teste requerem autocura na suíte de testes", async () => {
    const engine = new SelfHealingEngine();
    const result = await engine.analyzeAndRepairTests({
      allPassed: false,
      totalDurationMs: 100,
      totalRunners: 1,
      passedCount: 0,
      failedCount: 1,
      results: [
        {
          runnerName: "Unit Tests",
          type: "unit",
          command: "npm test",
          passed: false,
          exitCode: 1,
          durationMs: 100,
          stdout: "Fail",
          stderr: "AssertionError",
          errorDetails: "Assertion failed at tests/user.test.ts:15",
        },
      ],
    });

    expect(result.healed).toBe(true);
    expect(result.repairedTestFiles).toContain("Unit Tests");
  });
});
