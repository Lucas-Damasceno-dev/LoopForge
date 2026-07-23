import type { GuardrailsConfig } from "../config/schema.js";

export interface CircuitBreakerStatus {
  isOpen: boolean;
  consecutiveFailures: number;
  totalIterations: number;
  totalCostUsd: number;
  reason?: string;
}

export class CircuitBreaker {
  private maxFailures: number;
  private maxIterations: number;
  private maxBudgetUsd: number;
  private maxCostPerIteration: number;

  private consecutiveFailures: number = 0;
  private totalIterations: number = 0;
  private totalCostUsd: number = 0;

  constructor(config?: GuardrailsConfig) {
    this.maxFailures = config?.maxConsecutiveFailures ?? 3;
    this.maxIterations = config?.maxTotalIterations ?? 10;
    this.maxBudgetUsd = config?.maxBudgetUsd ?? 5.0;
    this.maxCostPerIteration = config?.maxCostPerIteration ?? 2.0;
  }

  public checkIterationCost(costUsd: number): { exceeded: boolean; reason?: string } {
    if (costUsd > this.maxCostPerIteration) {
      return {
        exceeded: true,
        reason: `Custo estimado da iteração ($${costUsd.toFixed(2)}) excede o orçamento por iteração ($${this.maxCostPerIteration.toFixed(2)}).`,
      };
    }
    return { exceeded: false };
  }

  public recordSuccess(costUsd: number = 0): CircuitBreakerStatus {
    this.consecutiveFailures = 0;
    this.totalIterations++;
    this.totalCostUsd += costUsd;

    if (costUsd > this.maxCostPerIteration) {
      return {
        isOpen: true,
        consecutiveFailures: this.consecutiveFailures,
        totalIterations: this.totalIterations,
        totalCostUsd: this.totalCostUsd,
        reason: `Custo por iteração excedeu o limite ($${costUsd.toFixed(2)} > $${this.maxCostPerIteration.toFixed(2)}). Circuit Breaker ATIVADO por custo de iteração.`,
      };
    }

    return this.evaluate();
  }

  public recordFailure(costUsd: number = 0): CircuitBreakerStatus {
    this.consecutiveFailures++;
    this.totalIterations++;
    this.totalCostUsd += costUsd;

    if (costUsd > this.maxCostPerIteration) {
      return {
        isOpen: true,
        consecutiveFailures: this.consecutiveFailures,
        totalIterations: this.totalIterations,
        totalCostUsd: this.totalCostUsd,
        reason: `Custo por iteração excedeu o limite ($${costUsd.toFixed(2)} > $${this.maxCostPerIteration.toFixed(2)}). Circuit Breaker ATIVADO por custo de iteração.`,
      };
    }

    return this.evaluate();
  }

  public evaluate(): CircuitBreakerStatus {
    if (this.consecutiveFailures >= this.maxFailures) {
      return {
        isOpen: true,
        consecutiveFailures: this.consecutiveFailures,
        totalIterations: this.totalIterations,
        totalCostUsd: this.totalCostUsd,
        reason: `Limite de falhas consecutivas atingido (${this.consecutiveFailures}/${this.maxFailures}). Circuit Breaker ATIVADO.`,
      };
    }

    if (this.totalIterations >= this.maxIterations) {
      return {
        isOpen: true,
        consecutiveFailures: this.consecutiveFailures,
        totalIterations: this.totalIterations,
        totalCostUsd: this.totalCostUsd,
        reason: `Limite máximo de iterações atingido (${this.totalIterations}/${this.maxIterations}). Loop finalizado por segurança.`,
      };
    }

    if (this.totalCostUsd >= this.maxBudgetUsd) {
      return {
        isOpen: true,
        consecutiveFailures: this.consecutiveFailures,
        totalIterations: this.totalIterations,
        totalCostUsd: this.totalCostUsd,
        reason: `Teto financeiro atingido ($${this.totalCostUsd.toFixed(2)}/$${this.maxBudgetUsd.toFixed(2)}). Circuit Breaker ATIVADO por custo.`,
      };
    }

    return {
      isOpen: false,
      consecutiveFailures: this.consecutiveFailures,
      totalIterations: this.totalIterations,
      totalCostUsd: this.totalCostUsd,
    };
  }

  public reset(): void {
    this.consecutiveFailures = 0;
    this.totalIterations = 0;
    this.totalCostUsd = 0;
  }
}
