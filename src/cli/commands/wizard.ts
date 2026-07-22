import * as path from "node:path";
import chalk from "chalk";
import { initCommand } from "./init.js";
import { bootstrapCommand } from "./bootstrap.js";

export async function wizardCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.bold.magenta(`\n🧙 Bem-vindo ao Assistente Guiado (Wizard) do LoopForge!\n`));
  console.log(chalk.cyan(`1. Gerando estrutura base de configuração e memórias...`));
  await initCommand(resolvedDir, "node-typescript");

  console.log(chalk.cyan(`2. Escaneando o repositório e gerando suíte de testes baseline...`));
  await bootstrapCommand(resolvedDir);

  console.log(chalk.bold.green(`\n✨ Configuração concluída com sucesso via Wizard!`));
  console.log(chalk.white(`Para iniciar a automação, execute: ${chalk.bold.cyan("npx loopforge run")}`));
}
