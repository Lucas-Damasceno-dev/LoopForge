import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";
import { LoopEngine } from "../../core/loop-engine.js";
import { logIterationStart, logIterationReport } from "../../ui/logger.js";
import { renderSummaryDashboard } from "../../ui/dashboard.js";
import { createGitHubPullRequest } from "../../git/pr.js";

export async function runCommand(targetDir: string = ".", options: { createPr?: boolean } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const config = await loadConfig(path.join(resolvedDir, ".loopforge.json"));
    console.log(chalk.cyan(`🚀 Iniciando LoopForge Engine para o projeto: '${config.projectName}'`));

    const engine = new LoopEngine(config, resolvedDir);

    const result = await engine.runLoop(async (_context, iteration, llmEngine) => {
      const activeModel = llmEngine.getActiveModel();
      logIterationStart(iteration, "creator", activeModel.model, activeModel.isFallback);
      return `Agente concluiu análise e ações para a iteração #${iteration}.`;
    });

    for (const report of result.reports) {
      logIterationReport(report);
    }

    renderSummaryDashboard(result);

    const reportPath = path.join(resolvedDir, ".loopforge/report.json");
    await fs.mkdir(path.dirname(reportPath), { recursive: true });
    await fs.writeFile(reportPath, JSON.stringify(result, null, 2), "utf-8");
    console.log(chalk.gray(`💾 Relatório de execução salvo em: ${reportPath}`));

    if (options.createPr) {
      console.log(chalk.cyan("\n🐙 Criando Pull Request no GitHub via GitHub CLI ('gh')..."));
      const prResult = await createGitHubPullRequest(result, { draft: true }, resolvedDir);
      if (prResult.success) {
        console.log(chalk.green(`✔ Pull Request criado com sucesso: ${prResult.url}`));
      } else {
        console.log(chalk.yellow(`⚠️ Não foi possível criar o PR: ${prResult.error}`));
      }
    }
  } catch (error: any) {
    console.error(chalk.red(`❌ Erro ao executar o LoopForge: ${error.message}`));
    process.exit(1);
  }
}
