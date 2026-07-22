import { describe, it, expect } from "vitest";
import { runSingleRunner, runHarness } from "../src/harness/runner.js";
import { parseRunnerErrors } from "../src/harness/parser.js";
import { formatHarnessFeedback } from "../src/harness/formatter.js";
import type { HarnessConfig, RunnerConfig } from "../src/config/schema.js";

describe("LoopForge Multi-Runner Harness Engine", () => {
  it("deve executar um runner com sucesso", async () => {
    const result = await runSingleRunner("Echo Test", "unit", "echo 'Success'", ".", 5000);
    expect(result.passed).toBe(true);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain("Success");
  });

  it("deve capturar falhas de execução e extrair detalhes do erro", async () => {
    const result = await runSingleRunner(
      "Fail Test",
      "unit",
      "node -e 'console.error(\"AssertionError: Expected true to be false\"); process.exit(1);'",
      ".",
      5000
    );
    expect(result.passed).toBe(false);
    expect(result.exitCode).toBe(1);
    expect(result.errorDetails).toContain("AssertionError");
  });

  it("deve executar múltiplos runners (Unit, Linter, E2E) e consolidar o sumário", async () => {
    const config: HarnessConfig = {
      parallel: true,
      stopOnFirstFailure: false,
      runners: [
        { name: "Unit Runner", type: "unit", command: "echo 'Unit OK'", timeoutMs: 5000, enabled: true },
        { name: "Linter Runner", type: "linter", command: "echo 'Linter OK'", timeoutMs: 5000, enabled: true },
        { name: "E2E Runner", type: "e2e", command: "echo 'E2E OK'", timeoutMs: 5000, enabled: true },
      ],
    };

    const summary = await runHarness(config);
    expect(summary.allPassed).toBe(true);
    expect(summary.passedCount).toBe(3);
    expect(summary.failedCount).toBe(0);
    expect(summary.results.length).toBe(3);
  });

  it("deve parsear erros de E2E corretamente", () => {
    const stdout = "";
    const stderr = "Error: page.click: TimeoutError: element not found\n  at /tests/e2e/login.spec.ts:15";

    const parsed = parseRunnerErrors("e2e", stdout, stderr);
    expect(parsed).toContain("TimeoutError");
    expect(parsed).toContain("element not found");
  });

  it("deve formatar feedback em Markdown quando há falhas", async () => {
    const config: HarnessConfig = {
      parallel: false,
      stopOnFirstFailure: false,
      runners: [
        { name: "Unit Test", type: "unit", command: "echo 'Unit OK'", timeoutMs: 5000, enabled: true },
        { name: "E2E Test", type: "e2e", command: "node -e 'console.error(\"Error: toBeVisible failed\"); process.exit(1);'", timeoutMs: 5000, enabled: true },
      ],
    };

    const summary = await runHarness(config);
    const feedback = formatHarnessFeedback(summary);

    expect(feedback).toContain("🚨 Diagnostic Harness Feedback (1/2 PASSANDO)");
    expect(feedback).toContain("Runner Falhou: E2E Test (E2E)");
    expect(feedback).toContain("toBeVisible failed");
  });
});
