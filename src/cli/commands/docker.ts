import * as path from "node:path";
import chalk from "chalk";
import { runInDockerContainer } from "../../git/docker.js";

export async function dockerRunCommand(command: string, image: string = "node:20-alpine", targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.cyan(`🐳 Executando comando no Docker Container (${image}): "${command}"...`));
  const res = await runInDockerContainer(command, image, resolvedDir);

  if (res.usedFallback) {
    console.log(chalk.yellow(`ℹ️ Executado via fallback local:`));
  } else {
    console.log(chalk.green(`✔ Executado dentro do Docker Sandbox:`));
  }

  console.log(chalk.gray(res.output));
}
