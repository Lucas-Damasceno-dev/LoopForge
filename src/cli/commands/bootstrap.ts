import * as path from "node:path";
import chalk from "chalk";
import { bootstrapHarness } from "../../harness/bootstrap.js";

export async function bootstrapCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    console.log(chalk.cyan("🔍 Analisando repositório para inicialização automática do Harness..."));

    const result = await bootstrapHarness(resolvedDir);

    console.log(chalk.green("\n✔ Auto-Harness Bootstrap concluído com sucesso!"));
    console.log(`  Stack Detectada: ${chalk.bold.yellow(result.stackDetected)}`);
    console.log(`  Runners Adicionados: ${chalk.bold(result.runnersAdded.length)} (${result.runnersAdded.map((r) => r.name).join(", ")})`);

    if (result.createdFiles.length > 0) {
      console.log(chalk.cyan("\n  Arquivos de teste criados:"));
      for (const file of result.createdFiles) {
        console.log(chalk.gray(`   - ${file}`));
      }
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(chalk.red(`❌ Falha ao executar Auto-Harness Bootstrap: ${msg}`));
    process.exit(1);
  }
}
