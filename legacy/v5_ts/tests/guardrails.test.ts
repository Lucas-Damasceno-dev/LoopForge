import { describe, it, expect } from "vitest";
import { CircuitBreaker } from "../src/guardrails/circuit-breaker.js";

describe("LoopForge Circuit Breaker Guardrails", () => {
  it("deve disparar circuit breaker após atuar o limite de falhas consecutivas", () => {
    const cb = new CircuitBreaker({
      maxTotalIterations: 10,
      maxConsecutiveFailures: 3,
      maxBudgetUsd: 5.0,
      requireCleanGit: false,
    });

    cb.recordFailure(0.01); // 1
    let status = cb.evaluate();
    expect(status.isOpen).toBe(false);

    cb.recordFailure(0.01); // 2
    status = cb.evaluate();
    expect(status.isOpen).toBe(false);

    cb.recordFailure(0.01); // 3
    status = cb.evaluate();
    expect(status.isOpen).toBe(true);
    expect(status.reason).toContain("Limite de falhas consecutivas atingido");
  });

  it("deve resetar o contador de falhas consecutivas após um resultado positivo", () => {
    const cb = new CircuitBreaker({
      maxTotalIterations: 10,
      maxConsecutiveFailures: 3,
      maxBudgetUsd: 5.0,
      requireCleanGit: false,
    });

    cb.recordFailure(0);
    cb.recordFailure(0);

    const statusSuccess = cb.recordSuccess(0);
    expect(statusSuccess.consecutiveFailures).toBe(0);

    const statusFail = cb.recordFailure(0);
    expect(statusFail.isOpen).toBe(false);
    expect(statusFail.consecutiveFailures).toBe(1);
  });

  it("deve interromper ao atingir o maxIterations", () => {
    const cb = new CircuitBreaker({
      maxTotalIterations: 2,
      maxConsecutiveFailures: 5,
      maxBudgetUsd: 5.0,
      requireCleanGit: false,
    });

    cb.recordFailure(0);
    cb.recordFailure(0);

    const status = cb.evaluate();
    expect(status.isOpen).toBe(true);
    expect(status.reason).toContain("Limite máximo de iterações atingido");
  });
});
