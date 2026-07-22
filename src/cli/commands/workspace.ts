import * as path from "node:path";
import chalk from "chalk";
import { WorkspaceOrchestrator } from "../../core/workspace.js";

export async function workspaceCommand(workspaceFile: string = "loopforge-workspace.json", targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    console.log(chalk.cyan(`🏢 Iniciando Orquestrador Multi-Repositório LoopForge Workspace...`));
    const orchestrator = new WorkspaceOrchestrator(workspaceFile);
    const results = await orchestrator.runWorkspaceLoops(resolvedDir);

    console.log(chalk.bold(`\n📊 Sumário de Execução do Workspace:`));
    for (const res of results) {
      if (res.success) {
        console.log(chalk.green(`  ✔ Repositório ${res.project}: CONCLUÍDO COM SUCESSO`));
      } else {
        console.log(chalk.red(`  ❌ Repositório ${res.project}: FALHOU`));
      }
    }
  } catch (err: any) {
    console.error(chalk.red(`❌ Erro ao executar workspace: ${err.message}`));
  }
}
