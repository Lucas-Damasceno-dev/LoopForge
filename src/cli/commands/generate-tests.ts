import * as path from "node:path";
import chalk from "chalk";
import { TestGenerator } from "../../harness/test-generator.js";

export async function generateTestsCommand(targetDir: string = ".", options: { dryRun?: boolean } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);
  const isDry = !!options.dryRun;

  console.log(chalk.cyan(`🧪 Analisando código não coberto para geração de testes com IA (Dry Run: ${isDry ? "SIM" : "NÃO"})...`));
  const generator = new TestGenerator();
  const created = await generator.generateTestsForUncoveredCode(resolvedDir, isDry);

  if (created.length === 0) {
    console.log(chalk.green(`✔ Todos os arquivos de código já possuem testes correspondentes.`));
  } else {
    console.log(chalk.bold.green(`\n✔ ${created.length} arquivo(s) de teste analisado(s):`));
    console.log(chalk.cyan(`─`.repeat(70)));
    for (const item of created) {
      console.log(`${chalk.bold.yellow(item.sourceFile)} ➔ ${chalk.bold.green(item.testFile)} ${isDry ? chalk.magenta("[DRY RUN]") : ""}`);
      console.log(chalk.gray(` Snippet: ${item.contentSnippet.replace(/\n/g, " ")}`));
      console.log(chalk.cyan(`─`.repeat(70)));
    }
  }
}
