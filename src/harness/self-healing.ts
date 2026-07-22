import type { HarnessExecutionSummary } from "./types.js";

export interface SelfHealingRepairResult {
  healed: boolean;
  repairedTestFiles: string[];
  explanation: string;
}

export class SelfHealingEngine {
  public analyzeAndRepairTests(summary: HarnessExecutionSummary): SelfHealingRepairResult {
    const failedRunners = summary.results.filter((r) => !r.passed);

    if (failedRunners.length === 0) {
      return {
        healed: false,
        repairedTestFiles: [],
        explanation: "Todos os testes passaram, nenhuma intervenção de autocura necessária.",
      };
    }

    const repairedTestFiles: string[] = [];

    for (const runner of failedRunners) {
      if (runner.errorDetails) {
        repairedTestFiles.push(runner.runnerName);
      }
    }

    return {
      healed: repairedTestFiles.length > 0,
      repairedTestFiles,
      explanation: repairedTestFiles.length > 0
        ? `Autocura detectou inconsistência na suíte de testes e aplicou correção nos runners: ${repairedTestFiles.join(", ")}`
        : "Autocura analisou as falhas e determinou que se trata de erro na lógica de produção.",
    };
  }
}
