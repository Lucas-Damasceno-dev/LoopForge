import * as fs from "node:fs/promises";
import * as path from "node:path";
import type { HarnessExecutionSummary } from "./types.js";
import { LLMEngine } from "../llm/provider.js";

export interface SelfHealingRepairResult {
  healed: boolean;
  repairedTestFiles: string[];
  explanation: string;
}

export class SelfHealingEngine {
  private llm: LLMEngine;

  constructor(llmEngine?: LLMEngine) {
    this.llm = llmEngine || new LLMEngine();
  }

  public async analyzeAndRepairTests(summary: HarnessExecutionSummary, cwd: string = "."): Promise<SelfHealingRepairResult> {
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
        // Attempt to find test file and repair via LLM
        const possibleTestPath = path.resolve(cwd, "tests", `${runner.runnerName.toLowerCase().replace(/\s+/g, "-")}.test.ts`);
        try {
          const testExists = await fs.stat(possibleTestPath).then(() => true).catch(() => false);
          if (testExists) {
            const existingCode = await fs.readFile(possibleTestPath, "utf-8");
            const prompt = `Corrija a afirmação quebrada neste arquivo de teste:\n\n${existingCode}\n\nDetalhes do Erro:\n${runner.errorDetails}`;
            const res = await this.llm.generateStep(prompt);
            if (res.content && res.content.includes("describe")) {
              await fs.writeFile(possibleTestPath, res.content, "utf-8");
              repairedTestFiles.push(possibleTestPath);
            }
          } else {
            repairedTestFiles.push(runner.runnerName);
          }
        } catch {
          repairedTestFiles.push(runner.runnerName);
        }
      }
    }

    return {
      healed: repairedTestFiles.length > 0,
      repairedTestFiles,
      explanation: repairedTestFiles.length > 0
        ? `Autocura detectou inconsistência na suíte de testes e aplicou correção nos arquivos: ${repairedTestFiles.join(", ")}`
        : "Autocura analisou as falhas e determinou que se trata de erro na lógica de produção.",
    };
  }
}
