import * as path from "node:path";
import chalk from "chalk";
import { WorkspaceOrchestrator } from "../../core/workspace.js";

export async function workspaceCommand(
  workspaceFile: string = "loopforge-workspace.json",
  targetDir: string = ".",
  options: { parallel?: boolean; concurrency?: string; format?: "json" | "text" } = {}
): Promise<void> {
  const resolvedDir = path.resolve(targetDir);
  const concurrencyNum = options.concurrency ? parseInt(options.concurrency, 10) : 3;

  try {
    if (options.format !== "json") {
      const modeText = options.parallel ? ` (PARALELO - Concorrência max: ${concurrencyNum})` : " (SEQUANCIAL)";
      console.log(chalk.cyan(`🏢 Iniciando Orquestrador Multi-Repositório LoopForge Workspace${modeText}...`));
    }

    const orchestrator = new WorkspaceOrchestrator(workspaceFile);
    const results = await orchestrator.runWorkspaceLoops(resolvedDir, {
      parallel: options.parallel,
      concurrency: concurrencyNum,
    });

    if (options.format === "json") {
      console.log(JSON.stringify({ workspaceFile, results }, null, 2));
      return;
    }

    console.log(chalk.bold(`\n📊 Sumário de Execução do Workspace:`));
    for (const res of results) {
      if (res.success) {
        console.log(chalk.green(`  ✔ Repositório ${res.project}: CONCLUÍDO COM SUCESSO`));
      } else {
        console.log(chalk.red(`  ❌ Repositório ${res.project}: FALHOU (${res.error || "Erro desconhecido"})`));
      }
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (options.format === "json") {
      console.log(JSON.stringify({ error: msg }));
    } else {
      console.error(chalk.red(`❌ Erro ao executar workspace: ${msg}`));
    }
  }
}
