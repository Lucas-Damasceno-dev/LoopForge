import * as path from "node:path";
import chalk from "chalk";
import { runInDockerContainer } from "../../git/docker.js";

export async function dockerRunCommand(command: string, targetDir: string = ".", options: { image?: string } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);
  const image = options.image || "node:20-alpine";

  console.log(chalk.cyan(`🐳 Executando comando no Docker Container (${image}): "${command}"...`));
  const res = await runInDockerContainer(command, resolvedDir, { image });

  if (res.usedFallback) {
    console.log(chalk.yellow(`ℹ️ Executado via fallback local:`));
  } else {
    console.log(chalk.green(`✔ Executado dentro do Docker Sandbox:`));
  }

  console.log(chalk.gray(res.output));
}
