import type { LoopForgeConfig } from "../config/schema.js";
import { runAllHarness } from "../harness/runner.js";
import { formatHarnessFeedback } from "../harness/formatter.js";
import type { HarnessExecutionSummary } from "../harness/types.js";
import { loadActiveSkills, formatSkillsPrompt } from "../skills/loader.js";
import { readMemoryFile, appendLesson, formatMemoryPrompt, updateHandoff } from "../memory/manager.js";
import { CircuitBreaker } from "../guardrails/circuit-breaker.js";
import { createCheckpoint, rollbackToCheckpoint } from "../git/checkpoint.js";

export type AgentStepRunner = (promptContext: string, iteration: number) => Promise<string>;

export interface IterationReport {
  iteration: number;
  passed: boolean;
  harnessSummary: HarnessExecutionSummary;
  agentResponse: string;
  rollbackExecuted: boolean;
  circuitBreakerTripped: boolean;
  stopReason?: string;
}

export interface LoopExecutionResult {
  success: boolean;
  totalIterations: number;
  reports: IterationReport[];
  stopReason: string;
}

export class LoopEngine {
  private circuitBreaker: CircuitBreaker;

  constructor(
    private config: LoopForgeConfig,
    private cwd: string = "."
  ) {
    this.circuitBreaker = new CircuitBreaker(config.guardrails);
  }

  public async runLoop(stepRunner: AgentStepRunner): Promise<LoopExecutionResult> {
    const reports: IterationReport[] = [];
    let lastHarnessFeedback = "";

    while (true) {
      const status = this.circuitBreaker.nextIteration();
      if (status.stop) {
        return {
          success: false,
          totalIterations: reports.length,
          reports,
          stopReason: status.reason || "Interrompido por Guardrail.",
        };
      }

      const iteration = status.currentIteration;

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

      // 2. Construir Prompt de Contexto da Iteração
      const fullContext = [
        `# 🔄 LoopForge Iteração #${iteration} [Estratégia: ${this.config.strategy.toUpperCase()}]`,
        skillsPrompt,
        memoryPrompt,
        lastHarnessFeedback,
      ]
        .filter(Boolean)
        .join("\n\n");

      // 3. Executar o Passo do Agente
      const agentResponse = await stepRunner(fullContext, iteration);

      // 4. Executar Harness (Sensores: Unit, Linter, E2E)
      const harnessSummary = await runAllHarness(this.config.harness.runners, this.cwd);

      // 5. Atualizar Circuit Breaker
      const breakerResult = this.circuitBreaker.recordResult(harnessSummary.allPassed);

      let rollbackExecuted = false;

      // 6. Lógica de Creator Loop, Memória e Rollback
      if (harnessSummary.allPassed) {
        lastHarnessFeedback = formatHarnessFeedback(harnessSummary);

        if (this.config.strategy === "creator" && this.config.guardrails.allowGitRollback) {
          await createCheckpoint(`Iteração #${iteration} passou no harness`, this.cwd);
        }

        await updateHandoff(
          this.config.memory.handoffFile,
          `# 🤝 Handoff Status\n- Iteração #${iteration} concluída com sucesso.\n- Último agente: ${agentResponse.slice(0, 100)}...`
        );

        const report: IterationReport = {
          iteration,
          passed: true,
          harnessSummary,
          agentResponse,
          rollbackExecuted: false,
          circuitBreakerTripped: breakerResult.stop,
        };
        reports.push(report);

        if (this.config.guardrails.stopOnSuccess) {
          return {
            success: true,
            totalIterations: reports.length,
            reports,
            stopReason: `✅ SUCESSO: Todos os runners do Harness passaram na iteração #${iteration}.`,
          };
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
            `Iteração #${iteration} falhou nos runners: ${failedNames}. Ajuste abordagens que provocam estes erros.`
          );
        }

        if (this.config.strategy === "creator" && this.config.guardrails.allowGitRollback) {
          rollbackExecuted = await rollbackToCheckpoint(this.cwd);
        }

        const report: IterationReport = {
          iteration,
          passed: false,
          harnessSummary,
          agentResponse,
          rollbackExecuted,
          circuitBreakerTripped: breakerResult.stop,
          stopReason: breakerResult.reason,
        };
        reports.push(report);

        if (breakerResult.stop) {
          return {
            success: false,
            totalIterations: reports.length,
            reports,
            stopReason: breakerResult.reason || "Disparo do Circuit Breaker.",
          };
        }
      }
    }
  }
}
