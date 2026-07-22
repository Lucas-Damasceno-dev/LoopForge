import * as path from "node:path";
import chalk from "chalk";
import { generateAnalyticsReport } from "../../telemetry/analytics.js";

export async function analyticsCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.cyan(`📊 Compilando métricas de telemetria e gerando relatório visual...`));
  const { summary, reportHtmlPath } = await generateAnalyticsReport(resolvedDir);

  console.log(chalk.green(`✔ Relatório gerado com sucesso!`));
  console.log(chalk.gray(`  - Iterações: ${summary.totalIterations}`));
  console.log(chalk.gray(`  - Tokens: ${summary.totalTokensUsed}`));
  console.log(chalk.gray(`  - Custo Total: $${summary.totalCostUsd.toFixed(4)}`));
  console.log(chalk.bold.yellow(`📄 Arquivo HTML: ${reportHtmlPath}`));
}
