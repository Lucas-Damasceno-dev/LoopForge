import type { LoopForgeConfig } from "../config/schema.js";
import { runHarness } from "../harness/runner.js";
import { formatHarnessFeedback } from "../harness/formatter.js";
import type { HarnessExecutionSummary } from "../harness/types.js";
import { MemoryManager } from "../memory/manager.js";
import { CircuitBreaker } from "../guardrails/circuit-breaker.js";
import { createCheckpoint, rollbackToCheckpoint } from "../git/checkpoint.js";
import { createSandboxBranch, mergeSandboxBranch, cleanupSandboxBranch, type SandboxInfo } from "../git/sandbox.js";
import { LLMEngine, type LLMResponse } from "../llm/provider.js";

export type AgentStepRunner = (promptContext: string, iteration: number, llmEngine: LLMEngine) => Promise<string>;

export interface IterationReport {
  iteration: number;
  passed: boolean;
  harnessSummary: HarnessExecutionSummary;
  agentResponse: string;
  modelUsed: string;
  isFallbackModel: boolean;
  tokensUsed: number;
  estimatedCostUsd: number;
  rollbackExecuted: boolean;
  circuitBreakerTripped: boolean;
  stopReason?: string;
}

export interface LoopExecutionResult {
  success: boolean;
  totalIterations: number;
  totalTokensUsed: number;
  totalCostUsd: number;
  sandboxBranchUsed?: string;
  reports: IterationReport[];
  stopReason: string;
}

export class LoopEngine {
  private circuitBreaker: CircuitBreaker;
  private llmEngine: LLMEngine;
  private memoryManager: MemoryManager;

  constructor(
    private config: LoopForgeConfig,
    private cwd: string = "."
  ) {
    this.circuitBreaker = new CircuitBreaker(config.guardrails);
    this.llmEngine = new LLMEngine(config.llm);
    this.memoryManager = new MemoryManager(config.memory, cwd);
  }

  public async runLoop(customStepRunner?: AgentStepRunner): Promise<LoopExecutionResult> {
    const reports: IterationReport[] = [];
    let lastHarnessFeedback = "";
    let sandboxInfo: SandboxInfo | null = null;

    try {
      sandboxInfo = await createSandboxBranch("loopforge/task-", this.cwd);
    } catch {
      // Sandbox branch creation failed (e.g. not a git repository); fallback to working dir
      sandboxInfo = null;
    }

    try {
      let iteration = 0;
      while (true) {
        iteration++;
        const status = this.circuitBreaker.evaluate();
        if (status.isOpen) {
          if (sandboxInfo) {
            await cleanupSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
          }
          return this.buildExecutionResult(false, reports, status.reason || "Interrompido por Guardrail.", sandboxInfo?.sandboxBranch);
        }

        // 1. Carregar Memórias
        const lessonsText = await this.memoryManager.readLessonsPrompt();
        const handoffText = await this.memoryManager.readHandoffPrompt();

        // 2. Construir Contexto do Prompt
        const fullContext = [
          `# 🔄 LoopForge Iteração #${iteration}`,
          lessonsText,
          handoffText,
          lastHarnessFeedback,
        ]
          .filter(Boolean)
          .join("\n\n");

        // 3. Executar o LLM / Agent Step
        let llmResponse: LLMResponse;
        if (customStepRunner) {
          const content = await customStepRunner(fullContext, iteration, this.llmEngine);
          const activeModelInfo = this.llmEngine.getActiveModel();
          llmResponse = {
            content,
            modelUsed: activeModelInfo.model,
            isFallback: activeModelInfo.isFallback,
            tokensUsed: Math.ceil((fullContext.length + content.length) / 4),
            estimatedCostUsd: activeModelInfo.isFallback ? 0.003 : 0.0,
          };
        } else {
          llmResponse = await this.llmEngine.generateStep(fullContext);
        }

        // 4. Executar o Harness Engine
        const harnessSummary = await runHarness(this.config.harness, this.cwd);
        this.llmEngine.registerHarnessResult(harnessSummary.allPassed);

        let rollbackExecuted = false;

        if (harnessSummary.allPassed) {
          lastHarnessFeedback = formatHarnessFeedback(harnessSummary);
          await createCheckpoint(`Iteração #${iteration} passou no harness`, this.cwd);
          await this.memoryManager.updateHandoff(`Iteração #${iteration} concluída`, "Manter automação ativa", this.cwd);

          const breakerStatus = this.circuitBreaker.recordSuccess(llmResponse.estimatedCostUsd);

          const report: IterationReport = {
            iteration,
            passed: true,
            harnessSummary,
            agentResponse: llmResponse.content,
            modelUsed: llmResponse.modelUsed,
            isFallbackModel: llmResponse.isFallback,
            tokensUsed: llmResponse.tokensUsed,
            estimatedCostUsd: llmResponse.estimatedCostUsd,
            rollbackExecuted: false,
            circuitBreakerTripped: breakerStatus.isOpen,
          };
          reports.push(report);

          if (sandboxInfo) {
            await mergeSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
          }

          return this.buildExecutionResult(
            true,
            reports,
            `✅ SUCESSO: Todos os runners do Harness passaram na iteração #${iteration}.`,
            sandboxInfo?.sandboxBranch
          );
        } else {
          // Falha no Harness
          lastHarnessFeedback = formatHarnessFeedback(harnessSummary);
          const failedNames = harnessSummary.results.filter((r) => !r.passed).map((r) => r.runnerName).join(", ");
          await this.memoryManager.appendLesson(
            `Falha nos runners: ${failedNames}`,
            `Ajustar lógica de código na iteração #${iteration}`
          );

          rollbackExecuted = await rollbackToCheckpoint(this.cwd);
          const breakerStatus = this.circuitBreaker.recordFailure(llmResponse.estimatedCostUsd);

          const report: IterationReport = {
            iteration,
            passed: false,
            harnessSummary,
            agentResponse: llmResponse.content,
            modelUsed: llmResponse.modelUsed,
            isFallbackModel: llmResponse.isFallback,
            tokensUsed: llmResponse.tokensUsed,
            estimatedCostUsd: llmResponse.estimatedCostUsd,
            rollbackExecuted,
            circuitBreakerTripped: breakerStatus.isOpen,
            stopReason: breakerStatus.reason,
          };
          reports.push(report);

          if (breakerStatus.isOpen) {
            if (sandboxInfo) {
              await cleanupSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
            }
            return this.buildExecutionResult(
              false,
              reports,
              breakerStatus.reason || "Disparo do Circuit Breaker.",
              sandboxInfo?.sandboxBranch
            );
          }
        }
      }
    } catch (error: unknown) {
      if (sandboxInfo) {
        await cleanupSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
      }
      throw error;
    }
  }

  private buildExecutionResult(
    success: boolean,
    reports: IterationReport[],
    stopReason: string,
    sandboxBranchUsed?: string
  ): LoopExecutionResult {
    const totalTokensUsed = reports.reduce((acc, r) => acc + r.tokensUsed, 0);
    const totalCostUsd = Number(reports.reduce((acc, r) => acc + r.estimatedCostUsd, 0).toFixed(6));

    return {
      success,
      totalIterations: reports.length,
      totalTokensUsed,
      totalCostUsd,
      sandboxBranchUsed,
      reports,
      stopReason,
    };
  }
}
