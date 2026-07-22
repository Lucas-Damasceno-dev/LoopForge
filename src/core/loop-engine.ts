import type { LoopForgeConfig } from "../config/schema.js";
import { runAllHarness } from "../harness/runner.js";
import { formatHarnessFeedback } from "../harness/formatter.js";
import type { HarnessExecutionSummary } from "../harness/types.js";
import { loadActiveSkills, formatSkillsPrompt } from "../skills/loader.js";
import { readMemoryFile, appendLesson, formatMemoryPrompt, updateHandoff } from "../memory/manager.js";
import { CircuitBreaker } from "../guardrails/circuit-breaker.js";
import { createCheckpoint, rollbackToCheckpoint } from "../git/checkpoint.js";
import { createSandboxBranch, mergeSandboxBranch, cleanupSandboxBranch, type SandboxInfo } from "../git/sandbox.js";
import { LLMEngine, type LLMResponse, type TokenUsage } from "../llm/provider.js";

export type AgentStepRunner = (promptContext: string, iteration: number, llmEngine: LLMEngine) => Promise<string>;

export interface IterationReport {
  iteration: number;
  passed: boolean;
  harnessSummary: HarnessExecutionSummary;
  agentResponse: string;
  modelUsed: string;
  isFallbackModel: boolean;
  tokens: TokenUsage;
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

  constructor(
    private config: LoopForgeConfig,
    private cwd: string = "."
  ) {
    this.circuitBreaker = new CircuitBreaker(config.guardrails);
    const providerConfig = config.provider || {
      name: "opencode",
      model: "deepseek-v3",
      fallbackModel: "anthropic/claude-3-5-sonnet",
      enableModelFallback: true,
      fallbackFailureThreshold: 2,
    };
    this.llmEngine = new LLMEngine(providerConfig);
  }

  public async runLoop(customStepRunner?: AgentStepRunner): Promise<LoopExecutionResult> {
    const reports: IterationReport[] = [];
    let lastHarnessFeedback = "";
    let sandboxInfo: SandboxInfo | null = null;

    const sandboxConfig = this.config.sandbox || { enableBranchSandbox: false, branchPrefix: "loopforge/task-" };

    // Criar Sandbox Branch se ativado
    if (sandboxConfig.enableBranchSandbox) {
      sandboxInfo = await createSandboxBranch(sandboxConfig.branchPrefix || "loopforge/task-", this.cwd);
    }

    try {
      while (true) {
        const status = this.circuitBreaker.nextIteration();
        if (status.stop) {
          if (sandboxInfo) {
            await cleanupSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
          }
          return this.buildExecutionResult(false, reports, status.reason || "Interrompido por Guardrail.", sandboxInfo?.sandboxBranch);
        }

        const iteration = status.currentIteration;
        const consecutiveFailures = status.consecutiveFailures;

        // 1. Carregar Skills e Memórias
        const { loadedSkills } = await loadActiveSkills(this.config.skills, this.cwd);
        const skillsPrompt = formatSkillsPrompt(loadedSkills);

        const lessonsText = await readMemoryFile(
          this.config.memory.lessonsFile,
          "🧠 Lições Aprendidas (Lessons Learned)"
        );
        const handoffText = await readMemoryFile(
          this.config.memory.handoffFile,
          "🤝 Instruções de Transição (Handoff)"
        );
        const memoryPrompt = formatMemoryPrompt(lessonsText, handoffText);

        // 2. Construir Contexto do Prompt
        const fullContext = [
          `# 🔄 LoopForge Iteração #${iteration} [Estratégia: ${this.config.strategy.toUpperCase()}]`,
          skillsPrompt,
          memoryPrompt,
          lastHarnessFeedback,
        ]
          .filter(Boolean)
          .join("\n\n");

        // 3. Executar o LLM / Agent Step (com OpenCode DeepSeek v4 free ou Model Fallback)
        let llmResponse: LLMResponse;
        if (customStepRunner) {
          const content = await customStepRunner(fullContext, iteration, this.llmEngine);
          const activeModelInfo = this.llmEngine.getActiveModel(consecutiveFailures);
          llmResponse = {
            content,
            modelUsed: activeModelInfo.model,
            isFallback: activeModelInfo.isFallback,
            tokens: {
              promptTokens: Math.ceil(fullContext.length / 4),
              completionTokens: Math.ceil(content.length / 4),
              totalTokens: Math.ceil((fullContext.length + content.length) / 4),
              estimatedCostUsd: activeModelInfo.isFallback ? 0.003 : 0.0,
            },
          };
        } else {
          llmResponse = await this.llmEngine.generateStep(fullContext, consecutiveFailures, this.cwd);
        }

        // 4. Executar o Harness Engine (Unit, Linter, E2E)
        const harnessSummary = await runAllHarness(this.config.harness.runners, this.cwd);

        // 5. Atualizar Circuit Breaker
        const breakerResult = this.circuitBreaker.recordResult(harnessSummary.allPassed);

        let rollbackExecuted = false;

        if (harnessSummary.allPassed) {
          lastHarnessFeedback = formatHarnessFeedback(harnessSummary);

          if (this.config.strategy === "creator" && this.config.guardrails.allowGitRollback) {
            await createCheckpoint(`Iteração #${iteration} passou no harness`, this.cwd);
          }

          await updateHandoff(
            this.config.memory.handoffFile,
            `# 🤝 Handoff Status\n- Iteração #${iteration} concluída com sucesso.\n- Modelo: ${llmResponse.modelUsed}\n- Resposta: ${llmResponse.content.slice(0, 100)}...`
          );

          const report: IterationReport = {
            iteration,
            passed: true,
            harnessSummary,
            agentResponse: llmResponse.content,
            modelUsed: llmResponse.modelUsed,
            isFallbackModel: llmResponse.isFallback,
            tokens: llmResponse.tokens,
            rollbackExecuted: false,
            circuitBreakerTripped: breakerResult.stop,
          };
          reports.push(report);

          if (this.config.guardrails.stopOnSuccess) {
            // Realizar Merge da Sandbox Branch caso 100% de sucesso
            if (sandboxInfo) {
              await mergeSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
            }
            return this.buildExecutionResult(
              true,
              reports,
              `✅ SUCESSO: Todos os runners do Harness passaram na iteração #${iteration}.`,
              sandboxInfo?.sandboxBranch
            );
          }
        } else {
          // Falha no Harness
          lastHarnessFeedback = formatHarnessFeedback(harnessSummary);

          if (this.config.memory.autoUpdateLessons) {
            const failedNames = harnessSummary.results
              .filter((r) => !r.passed)
              .map((r) => r.runnerName)
              .join(", ");

            await appendLesson(
              this.config.memory.lessonsFile,
              `Iteração #${iteration} falhou nos runners: ${failedNames}. Modelo utilizado: ${llmResponse.modelUsed}. Ajuste abordagens que provocam este erro.`
            );
          }

          if (this.config.strategy === "creator" && this.config.guardrails.allowGitRollback) {
            rollbackExecuted = await rollbackToCheckpoint(this.cwd);
          }

          const report: IterationReport = {
            iteration,
            passed: false,
            harnessSummary,
            agentResponse: llmResponse.content,
            modelUsed: llmResponse.modelUsed,
            isFallbackModel: llmResponse.isFallback,
            tokens: llmResponse.tokens,
            rollbackExecuted,
            circuitBreakerTripped: breakerResult.stop,
            stopReason: breakerResult.reason,
          };
          reports.push(report);

          if (breakerResult.stop) {
            if (sandboxInfo) {
              await cleanupSandboxBranch(sandboxInfo.sandboxBranch, sandboxInfo.originalBranch, this.cwd);
            }
            return this.buildExecutionResult(
              false,
              reports,
              breakerResult.reason || "Disparo do Circuit Breaker.",
              sandboxInfo?.sandboxBranch
            );
          }
        }
      }
    } catch (error: any) {
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
    const totalTokensUsed = reports.reduce((acc, r) => acc + r.tokens.totalTokens, 0);
    const totalCostUsd = Number(reports.reduce((acc, r) => acc + r.tokens.estimatedCostUsd, 0).toFixed(6));

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
