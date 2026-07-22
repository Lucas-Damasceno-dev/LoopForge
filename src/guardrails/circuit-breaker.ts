import type { GuardrailsConfig } from "../config/schema.js";

export interface CircuitBreakerStatus {
  stop: boolean;
  reason?: string;
  consecutiveFailures: number;
  currentIteration: number;
}

export class CircuitBreaker {
  private currentIteration = 0;
  private consecutiveFailures = 0;
  private isTripped = false;
  private tripReason?: string;

  constructor(private config: GuardrailsConfig) {}

  public nextIteration(): CircuitBreakerStatus {
    this.currentIteration++;
    return this.checkStatus();
  }

  public recordResult(passed: boolean): CircuitBreakerStatus {
    if (passed) {
      this.consecutiveFailures = 0;
    } else {
      this.consecutiveFailures++;
    }

    if (this.consecutiveFailures >= this.config.maxConsecutiveFailures) {
      this.isTripped = true;
      this.tripReason = `🚨 CIRCUIT BREAKER DISPARADO: Excedido o limite de ${this.config.maxConsecutiveFailures} falha(s) consecutiva(s) no Harness.`;
    }

    if (this.currentIteration >= this.config.maxIterations && !passed) {
      this.isTripped = true;
      this.tripReason = `🛑 LIMITE DE ITERAÇÕES ALCANÇADO: Atingido o limite de ${this.config.maxIterations} iterações.`;
    }

    return this.checkStatus();
  }

  public checkStatus(): CircuitBreakerStatus {
    if (this.currentIteration > this.config.maxIterations) {
      return {
        stop: true,
        reason: `🛑 LIMITE DE ITERAÇÕES ALCANÇADO: Atingido o limite de ${this.config.maxIterations} iterações.`,
        consecutiveFailures: this.consecutiveFailures,
        currentIteration: this.currentIteration,
      };
    }

    if (this.isTripped) {
      return {
        stop: true,
        reason: this.tripReason,
        consecutiveFailures: this.consecutiveFailures,
        currentIteration: this.currentIteration,
      };
    }

    return {
      stop: false,
      consecutiveFailures: this.consecutiveFailures,
      currentIteration: this.currentIteration,
    };
  }

  public getIteration(): number {
    return this.currentIteration;
  }
}
