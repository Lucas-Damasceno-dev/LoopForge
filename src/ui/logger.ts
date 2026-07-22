import chalk from "chalk";
import type { IterationReport } from "../core/loop-engine.js";

export function logIterationStart(iteration: number, strategy: string, model: string, isFallback: boolean): void {
  console.log("\n" + chalk.bold.blue("─".repeat(60)));
  const modelText = isFallback
    ? chalk.bgRed.white.bold(` FALLBACK: ${model} `)
    : chalk.bgCyan.black.bold(` MODELO: ${model} (DEFAULT FREE) `);

  console.log(
    chalk.bold.cyan(`🔄 LoopForge Iteração #${iteration}`) +
      chalk.gray(` [Estratégia: ${strategy}] `) +
      modelText
  );
  console.log(chalk.bold.blue("─".repeat(60)));
}

export function logIterationReport(report: IterationReport): void {
  const summary = report.harnessSummary;

  if (report.passed) {
    console.log(
      chalk.bold.green(
        `✔ Iteração #${report.iteration} PASSOU em todos os runners (${summary.passedCount}/${summary.totalRunners} OK em ${summary.totalDurationMs}ms)`
      )
    );
  } else {
    console.log(chalk.bold.red(`❌ Iteração #${report.iteration} FALHOU (${summary.passedCount}/${summary.totalRunners} OK)`));
    if (report.rollbackExecuted) {
      console.log(chalk.yellow("  ↩ Rollback no Git executado para restaurar o estado limpo."));
    }
  }

  for (const runner of summary.results) {
    const icon = runner.passed ? chalk.green("✓") : chalk.red("✖");
    console.log(`   ${icon} ${runner.runnerName} (${runner.type.toUpperCase()}) - ${runner.durationMs}ms`);
  }

  console.log(
    chalk.gray(
      `   📊 Tokens: ${report.tokensUsed} | Custo Est.: $${report.estimatedCostUsd.toFixed(4)}`
    )
  );

  if (report.stopReason) {
    console.log(chalk.bold.yellow(`\n⚠️ Motivo de Parada: ${report.stopReason}`));
  }
}
