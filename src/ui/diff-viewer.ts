import chalk from "chalk";

export function renderDiffToTerminal(diffText: string): void {
  if (!diffText || !diffText.trim()) {
    console.log(chalk.gray("  (Nenhuma alteração detectada no código)"));
    return;
  }

  const lines = diffText.split("\n");
  console.log(chalk.bold.cyan("\n📜 Visualização de Alterações (Git Diff):\n"));

  for (const line of lines) {
    if (line.startsWith("diff --git") || line.startsWith("index ")) {
      console.log(chalk.bold.gray(line));
    } else if (line.startsWith("---") || line.startsWith("+++")) {
      console.log(chalk.bold.yellow(line));
    } else if (line.startsWith("@@")) {
      console.log(chalk.cyan(line));
    } else if (line.startsWith("+")) {
      console.log(chalk.green(line));
    } else if (line.startsWith("-")) {
      console.log(chalk.red(line));
    } else {
      console.log(chalk.white(line));
    }
  }
  console.log("");
}
