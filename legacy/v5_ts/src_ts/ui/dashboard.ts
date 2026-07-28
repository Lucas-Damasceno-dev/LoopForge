import chalk from "chalk";
import type { LoopExecutionResult } from "../core/loop-engine.js";

export function renderSummaryDashboard(result: LoopExecutionResult): void {
  console.log("\n" + chalk.bold.magenta("=").repeat(65));
  console.log(chalk.bold.magenta("📊 RESUMO FINAL DA EXECUÇÃO DO LOOPFORGE"));
  console.log(chalk.bold.magenta("=").repeat(65));

  const statusBadge = result.success
    ? chalk.bgGreen.black.bold(" SUCESSO ")
    : chalk.bgRed.white.bold(" INTERROMPIDO ");

  console.log(` Status Final:           ${statusBadge}`);
  console.log(` Total de Iterações:     ${chalk.bold(result.totalIterations)}`);
  console.log(` Total de Tokens Usados: ${chalk.bold(result.totalTokensUsed)}`);
  console.log(` Custo Estimado Total:   ${chalk.green(`$${result.totalCostUsd.toFixed(4)}`)}`);
  if (result.sandboxBranchUsed) {
    console.log(` Sandbox Branch:         ${chalk.cyan(result.sandboxBranchUsed)}`);
  }
  console.log(` Motivo de Parada:       ${chalk.yellow(result.stopReason)}`);

  console.log("\n" + chalk.bold("Histórico de Iterações:"));
  for (const report of result.reports) {
    const statusText = report.passed ? chalk.green("PASSOU") : chalk.red("FALHOU");
    const fallbackTag = report.isFallbackModel ? chalk.red(" [MODEL FALLBACK]") : chalk.gray(" [OpenCode DeepSeek]");
    const rollbackText = report.rollbackExecuted ? chalk.yellow(" [Git Rollback]") : "";
    console.log(
      `  Iteração #${report.iteration}: ${statusText}${fallbackTag}${rollbackText} (${report.harnessSummary.passedCount}/${report.harnessSummary.totalRunners} runners) - Model: ${report.modelUsed}`
    );

    if (report.diff && report.diff.trim()) {
      console.log(chalk.bold.gray(`    🔍 Diff da Iteração #${report.iteration}:`));
      const diffLines = report.diff.split("\n").slice(0, 15);
      for (const line of diffLines) {
        if (line.startsWith("+")) {
          console.log(chalk.green(`      ${line}`));
        } else if (line.startsWith("-")) {
          console.log(chalk.red(`      ${line}`));
        } else {
          console.log(chalk.gray(`      ${line}`));
        }
      }
      if (report.diff.split("\n").length > 15) {
        console.log(chalk.gray(`      ... [diff truncado]`));
      }
    }
  }
  console.log(chalk.bold.magenta("=").repeat(65) + "\n");
}
