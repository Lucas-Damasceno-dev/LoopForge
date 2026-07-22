import chalk from "chalk";
import type { LoopExecutionResult } from "../core/loop-engine.js";

export function renderSummaryDashboard(result: LoopExecutionResult): void {
  console.log("\n" + chalk.bold.magenta("=").repeat(60));
  console.log(chalk.bold.magenta("📊 RESUMO FINAL DA EXECUÇÃO DO LOOPFORGE"));
  console.log(chalk.bold.magenta("=").repeat(60));

  const statusBadge = result.success
    ? chalk.bgGreen.black.bold(" SUCESSO ")
    : chalk.bgRed.white.bold(" INTERROMPIDO ");

  console.log(` Status Final:       ${statusBadge}`);
  console.log(` Total de Iterações: ${chalk.bold(result.totalIterations)}`);
  console.log(` Motivo de Parada:   ${chalk.yellow(result.stopReason)}`);

  console.log("\n" + chalk.bold("Histórico de Iterações:"));
  for (const report of result.reports) {
    const statusText = report.passed ? chalk.green("PASSOU") : chalk.red("FALHOU");
    const rollbackText = report.rollbackExecuted ? chalk.yellow(" [Git Rollback]") : "";
    console.log(`  Iteração #${report.iteration}: ${statusText}${rollbackText} (${report.harnessSummary.passedCount}/${report.harnessSummary.totalRunners} runners)`);
  }
  console.log(chalk.bold.magenta("=").repeat(60) + "\n");
}
