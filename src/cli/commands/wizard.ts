import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { initCommand } from "./init.js";
import { bootstrapCommand } from "./bootstrap.js";

export async function wizardCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.bold.magenta(`\n🧙 Bem-vindo ao Assistente Guiado (Wizard) do LoopForge!\n`));

  let template = "node-typescript";
  const hasPyproject = await fs.stat(path.join(resolvedDir, "pyproject.toml")).then(() => true).catch(() => false);
  const hasCargoToml = await fs.stat(path.join(resolvedDir, "Cargo.toml")).then(() => true).catch(() => false);

  if (hasPyproject) template = "python-pytest";
  else if (hasCargoToml) template = "rust-cargo";

  console.log(chalk.cyan(`1. Gerando estrutura base para a stack auto-detectada: '${template}'...`));
  await initCommand(resolvedDir, template);

  console.log(chalk.cyan(`2. Escaneando o repositório e gerando suíte de testes baseline...`));
  await bootstrapCommand(resolvedDir);

  console.log(chalk.bold.green(`\n✨ Configuração concluída com sucesso via Wizard!`));
  console.log(chalk.white(`Para iniciar a automação, execute: ${chalk.bold.cyan("npx loopforge run")}`));
}
