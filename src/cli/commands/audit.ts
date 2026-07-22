import * as path from "node:path";
import chalk from "chalk";
import { SecurityScanner } from "../../guardrails/security-scanner.js";

export async function auditCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.cyan(`🛡️ Executando LoopForge AI Security Scanner...`));
  const scanner = new SecurityScanner();
  const vulnerabilities = await scanner.scanDirectory(resolvedDir);

  if (vulnerabilities.length === 0) {
    console.log(chalk.green(`\n✔ Nenhuma vulnerabilidade de segurança detectada no código!`));
  } else {
    console.log(chalk.red(`\n⚠️ ${vulnerabilities.length} vulnerabilidade(s) encontrada(s):`));
    for (const vulnp of vulnerabilities) {
      console.log(chalk.yellow(`  - [${vulnp.type.toUpperCase()}] ${vulnp.file}:${vulnp.line}`));
      console.log(chalk.gray(`    Snippet: "${vulnp.snippet}"`));
    }
  }
}
