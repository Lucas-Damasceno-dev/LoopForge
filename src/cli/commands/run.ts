import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";
import { LoopEngine } from "../../core/loop-engine.js";
import { logIterationStart, logIterationReport } from "../../ui/logger.js";
import { renderSummaryDashboard } from "../../ui/dashboard.js";
import { createGitHubPullRequest } from "../../git/pr.js";
import { isGitRepo } from "../../git/checkpoint.js";

export async function runCommand(targetDir: string = ".", options: { createPr?: boolean; watch?: boolean } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  const config = await loadConfig(undefined, resolvedDir);
  if (config.guardrails.requireCleanGit) {
    const isClean = await isGitRepo(resolvedDir);
    if (!isClean) {
      console.warn(chalk.yellow("⚠️ [Guardrail]: Repositório Git não está inicializado ou limpo. Prosseguindo em modo permissivo..."));
    }
  }

  let isExecuting = false;

  const executeOnce = async () => {
    if (isExecuting) return;
    isExecuting = true;

    try {
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
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      console.error(chalk.red(`❌ Erro ao executar o LoopForge: ${msg}`));
    } finally {
      isExecuting = false;
    }
  };

  await executeOnce();

  if (options.watch) {
    console.log(chalk.yellow(`\n👀 Modo --watch ATIVO: Aguardando modificações em arquivos .ts no diretório...`));
    let debounceTimer: NodeJS.Timeout | null = null;
    const watcher = fsSync.watch(resolvedDir, { recursive: true }, (_eventType, filename) => {
      if (filename && filename.endsWith(".ts") && !filename.includes("node_modules") && !filename.includes(".loopforge")) {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          console.log(chalk.cyan(`\n🔄 Modificação detectada em ${filename}. Re-executando LoopForge Engine...`));
          executeOnce();
        }, 500);
      }
    });

    process.on("SIGINT", () => {
      console.log(chalk.gray("\nEncerrando modo --watch..."));
      watcher.close();
      process.exit(0);
    });
  }
}
