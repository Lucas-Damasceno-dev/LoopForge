import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";
import { LoopEngine } from "../../core/loop-engine.js";
import { logIterationStart, logIterationReport } from "../../ui/logger.js";
import { renderSummaryDashboard } from "../../ui/dashboard.js";

export async function runCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const config = await loadConfig(path.join(resolvedDir, ".loopforge.json"));
    console.log(chalk.cyan(`🚀 Iniciando LoopForge Engine para o projeto: '${config.name}'`));

    const engine = new LoopEngine(config, resolvedDir);

    const result = await engine.runLoop(async (_context, iteration, llmEngine) => {
      const activeModel = llmEngine.getActiveModel(0);
      logIterationStart(iteration, config.strategy, activeModel.model, activeModel.isFallback);
      return `Agente concluiu análise e ações para a iteração #${iteration}.`;
    });

    for (const report of result.reports) {
      logIterationReport(report);
    }

    renderSummaryDashboard(result);

    // Salvar relatório de execução
    const reportPath = path.join(resolvedDir, ".loopforge/report.json");
    await fs.mkdir(path.dirname(reportPath), { recursive: true });
    await fs.writeFile(reportPath, JSON.stringify(result, null, 2), "utf-8");
    console.log(chalk.gray(`💾 Relatório de execução salvo em: ${reportPath}`));

  } catch (error: any) {
    console.error(chalk.red(`❌ Erro ao executar o LoopForge: ${error.message}`));
    process.exit(1);
  }
}
