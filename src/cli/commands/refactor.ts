import * as path from "node:path";
import chalk from "chalk";
import { RefactorEngine } from "../../core/refactor-engine.js";

export async function refactorCommand(rule: string, targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    console.log(chalk.cyan(`🛠️ Iniciando Motor de Auto-Refatoração LoopForge...`));
    console.log(chalk.yellow(`  Regra de Refatoração: "${rule}"`));

    const refactorEngine = new RefactorEngine(resolvedDir);
    const result = await refactorEngine.runRefactor({ rule });

    if (result.success) {
      console.log(chalk.green(`\n✔ Auto-Refatoração concluída com sucesso!`));
      console.log(chalk.gray(`  Blocos de código analisados: ${result.filesAnalyzed}`));
    } else {
      console.log(chalk.red(`\n❌ Auto-Refatoração encerrada com avisos: ${result.summary}`));
    }
  } catch (error: any) {
    console.error(chalk.red(`❌ Erro ao executar refatoração: ${error.message}`));
    process.exit(1);
  }
}
