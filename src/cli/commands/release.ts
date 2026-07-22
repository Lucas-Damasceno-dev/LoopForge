import * as path from "node:path";
import chalk from "chalk";
import { generateReleaseNotes } from "../../ci/release.js";

export async function releaseCommand(version: string = "3.1.0", targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.cyan(`📜 Gerando Release Notes semântico e atualizando CHANGELOG.md...`));
  const changelogPath = await generateReleaseNotes(version, resolvedDir);
  console.log(chalk.green(`✔ Release v${version} registrado em: ${changelogPath}`));
}
