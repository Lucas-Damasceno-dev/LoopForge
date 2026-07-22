import * as path from "node:path";
import chalk from "chalk";
import { TestGenerator } from "../../harness/test-generator.js";

export async function generateTestsCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.cyan(`🧪 Analisando código não coberto para geração autônoma de testes...`));
  const generator = new TestGenerator();
  const created = await generator.generateTestsForUncoveredCode(resolvedDir);

  if (created.length === 0) {
    console.log(chalk.green(`✔ Todos os arquivos de código já possuem testes correspondentes.`));
  } else {
    console.log(chalk.green(`\n✔ ${created.length} suíte(s) de teste(s) gerada(s) com sucesso:`));
    for (const item of created) {
      console.log(chalk.gray(`  - ${item.sourceFile} ➔ ${chalk.bold.yellow(item.testFile)}`));
    }
  }
}
