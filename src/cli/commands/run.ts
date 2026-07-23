import * as fs from "node:fs/promises";
import * as fsSync from "node:fs";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";
import { LoopEngine } from "../../core/loop-engine.js";
import { logIterationStart, logIterationReport } from "../../ui/logger.js";
import { renderSummaryDashboard } from "../../ui/dashboard.js";
import { reviewAndCreatePR } from "../../git/pr.js";
import { isGitRepo } from "../../git/checkpoint.js";
import { sendMultiChannelNotification } from "../../ci/notifications/index.js";

export async function runCommand(
  targetDir: string = ".",
  options: { createPr?: boolean; review?: boolean; auto?: boolean; watch?: boolean; format?: "json" | "text" } = {}
): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  let currentConfig = await loadConfig(undefined, resolvedDir);
  if (currentConfig.guardrails.requireCleanGit) {
    const isClean = await isGitRepo(resolvedDir);
    if (!isClean && options.format !== "json") {
      console.warn(chalk.yellow("⚠️ [Guardrail]: Repositório Git não está inicializado ou limpo. Prosseguindo em modo permissivo..."));
    }
  }

  let isExecuting = false;

  const executeOnce = async () => {
    if (isExecuting) return;
    isExecuting = true;

    try {
      if (options.format !== "json") {
        console.log(chalk.cyan(`🚀 Iniciando LoopForge Engine para o projeto: '${currentConfig.projectName}'`));
      }

      const engine = new LoopEngine(currentConfig, resolvedDir);

      const result = await engine.runLoop(async (_context, iteration, llmEngine) => {
        const activeModel = llmEngine.getActiveModel();
        if (options.format !== "json") {
          logIterationStart(iteration, "creator", activeModel.model, activeModel.isFallback);
        }
        return `Agente concluiu análise e ações para a iteração #${iteration}.`;
      });

      if (options.format === "json") {
        console.log(JSON.stringify(result, null, 2));
      } else {
        for (const report of result.reports) {
          logIterationReport(report);
        }
        renderSummaryDashboard(result);
      }

      const reportPath = path.join(resolvedDir, ".loopforge/report.json");
      await fs.mkdir(path.dirname(reportPath), { recursive: true });
      await fs.writeFile(reportPath, JSON.stringify(result, null, 2), "utf-8");
      if (options.format !== "json") {
        console.log(chalk.gray(`💾 Relatório de execução salvo em: ${reportPath}`));
      }

      // Send multi-channel notification
      await sendMultiChannelNotification(currentConfig.notifications, {
        title: `Execução do LoopForge em '${currentConfig.projectName}'`,
        message: `Loop concluído com ${result.totalIterations} iterações (Status: ${result.success ? "SUCESSO" : "FALHA"}). Motivo: ${result.stopReason}`,
        status: result.success ? "success" : "failure",
      });

      if (options.createPr || options.review) {
        if (options.format !== "json") {
          console.log(chalk.cyan("\n🐙 Processando Pull Request no GitHub via GitHub CLI ('gh')..."));
        }
        const prResult = await reviewAndCreatePR(
          result,
          { draft: true, review: options.review, auto: options.auto },
          resolvedDir
        );
        if (prResult.success) {
          if (options.format !== "json") {
            console.log(chalk.green(`✔ Pull Request criado com sucesso: ${prResult.url}`));
          }
        } else {
          if (options.format !== "json") {
            console.log(chalk.yellow(`⚠️ Não foi possível criar o PR: ${prResult.error}`));
          }
        }
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      if (options.format === "json") {
        console.log(JSON.stringify({ error: msg }));
      } else {
        console.error(chalk.red(`❌ Erro ao executar o LoopForge: ${msg}`));
      }
    } finally {
      isExecuting = false;
    }
  };

  await executeOnce();

  if (options.watch) {
    if (options.format !== "json") {
      console.log(chalk.yellow(`\n👀 Modo --watch ATIVO (com Hot-Reload de Config): Aguardando modificações em .ts ou .loopforge.json/.yml...`));
    }
    let debounceTimer: NodeJS.Timeout | null = null;
    const watcher = fsSync.watch(resolvedDir, { recursive: true }, async (_eventType, filename) => {
      if (!filename || filename.includes("node_modules") || filename.includes(".loopforge/report.json")) return;

      const isConfig = filename.includes(".loopforge");
      const isCode = filename.endsWith(".ts");

      if (isConfig || isCode) {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          if (isConfig) {
            console.log(chalk.magenta(`\n⚡ Hot-Reloading de Configurações detectado em ${filename}...`));
            try {
              currentConfig = await loadConfig(undefined, resolvedDir);
              console.log(chalk.green(`✔ Configuração recarregada com sucesso sem reiniciar o processo!`));
            } catch (err) {
              console.warn(chalk.yellow(`⚠️ Falha ao recarregar config em hot-reload: ${err}`));
            }
          } else {
            console.log(chalk.cyan(`\n🔄 Modificação detectada em ${filename}. Re-executando LoopForge Engine...`));
          }
          await executeOnce();
        }, 500);
      }
    });

    process.on("SIGINT", () => {
      if (options.format !== "json") {
        console.log(chalk.gray("\nEncerrando modo --watch..."));
      }
      watcher.close();
      process.exit(0);
    });
  }
}
