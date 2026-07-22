import { describe, it, expect } from "vitest";
import { CircuitBreaker } from "../src/guardrails/circuit-breaker.js";

describe("LoopForge Circuit Breaker Guardrails", () => {
  it("deve disparar circuit breaker após atuar o limite de falhas consecutivas", () => {
    const cb = new CircuitBreaker({
      maxIterations: 10,
      maxConsecutiveFailures: 3,
      stopOnSuccess: true,
      allowGitRollback: true,
    });

    cb.nextIteration(); // Iteração 1
    let status = cb.recordResult(false);
    expect(status.stop).toBe(false);

    cb.nextIteration(); // Iteração 2
    status = cb.recordResult(false);
    expect(status.stop).toBe(false);

    cb.nextIteration(); // Iteração 3
    status = cb.recordResult(false);
    expect(status.stop).toBe(true);
    expect(status.reason).toContain("CIRCUIT BREAKER DISPARADO");
  });

  it("deve resetar o contador de falhas consecutivas após um resultado positivo", () => {
    const cb = new CircuitBreaker({
      maxIterations: 10,
      maxConsecutiveFailures: 3,
      stopOnSuccess: true,
      allowGitRollback: true,
    });

    cb.nextIteration(); // 1
    cb.recordResult(false);
    cb.nextIteration(); // 2
    cb.recordResult(false);

    // Iteração 3 passa
    cb.nextIteration(); // 3
    const statusSuccess = cb.recordResult(true);
    expect(statusSuccess.consecutiveFailures).toBe(0);

    // Iteração 4 falha (agora é a primeira falha seguida)
    cb.nextIteration(); // 4
    const statusFail = cb.recordResult(false);
    expect(statusFail.stop).toBe(false);
    expect(statusFail.consecutiveFailures).toBe(1);
  });

  it("deve interromper ao atingir o maxIterations", () => {
    const cb = new CircuitBreaker({
      maxIterations: 2,
      maxConsecutiveFailures: 5,
      stopOnSuccess: true,
      allowGitRollback: true,
    });

    cb.nextIteration(); // 1
    cb.recordResult(false);
    cb.nextIteration(); // 2
    cb.recordResult(false);

    const status3 = cb.nextIteration(); // 3 (excede 2)
    expect(status3.stop).toBe(true);
    expect(status3.reason).toContain("LIMITE DE ITERAÇÕES ALCANÇADO");
  });
});
