import { describe, it, expect } from "vitest";
import { CodeLoopLockDetector } from "../src/guardrails/loop-lock.js";

describe("LoopForge Code Loop Lock Detector", () => {
  it("deve detectar respostas idênticas repetidas", () => {
    const detector = new CodeLoopLockDetector();

    const res1 = detector.registerResponse("const x = 1;");
    expect(res1.isLocked).toBe(false);

    const res2 = detector.registerResponse("const x = 1;");
    expect(res2.isLocked).toBe(true);
    expect(res2.warningPrompt).toContain("resposta idêntica");
  });
});
