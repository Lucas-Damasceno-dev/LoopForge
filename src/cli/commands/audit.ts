import * as path from "node:path";
import chalk from "chalk";
import { SecurityScanner } from "../../guardrails/security-scanner.js";

export async function auditCommand(targetDir: string = ".", options: { fix?: boolean; format?: "json" | "text" } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  if (options.format !== "json") {
    console.log(chalk.cyan(`🛡️ Executando LoopForge AI Security Scanner...`));
  }

  const scanner = new SecurityScanner();
  const vulnerabilities = await scanner.scanDirectory(resolvedDir);

  if (options.fix && vulnerabilities.length > 0) {
    const fixRes = await scanner.autoFixVulnerabilities(resolvedDir, vulnerabilities);
    if (options.format === "json") {
      console.log(JSON.stringify({ vulnerabilities, fixes: fixRes.fixes, fixedCount: fixRes.fixedCount }, null, 2));
      return;
    }

    console.log(chalk.green(`\n🔧 Auto-Fix concluído! ${fixRes.fixedCount} vulnerabilidade(s) corrigida(s):`));
    for (const fix of fixRes.fixes) {
      console.log(chalk.green(`  ✔ [${fix.type}] ${fix.file}:${fix.line} - ${fix.fixApplied}`));
    }
    return;
  }

  if (options.format === "json") {
    console.log(JSON.stringify({ vulnerabilities }, null, 2));
    return;
  }

  if (vulnerabilities.length === 0) {
    console.log(chalk.green(`\n✔ Nenhuma vulnerabilidade de segurança detectada no código!`));
  } else {
    console.log(chalk.red(`\n⚠️ ${vulnerabilities.length} vulnerabilidade(s) encontrada(s):`));
    for (const vulnp of vulnerabilities) {
      console.log(chalk.yellow(`  - [${vulnp.type.toUpperCase()}] ${vulnp.file}:${vulnp.line}`));
      console.log(chalk.gray(`    Snippet: "${vulnp.snippet}"`));
    }
    console.log(chalk.cyan(`\n💡 Dica: Execute 'loopforge audit --fix' para auto-corrigir vulnerabilidades.`));
  }
}
