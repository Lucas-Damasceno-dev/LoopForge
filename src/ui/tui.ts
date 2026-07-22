import chalk from "chalk";
import type { HarnessExecutionSummary } from "../harness/types.js";
import type { SwarmStepResult } from "../agents/swarm.js";

export function renderTUIDashboard(options: {
  iteration: number;
  strategy: string;
  activeModel: string;
  isFallback: boolean;
  harnessSummary?: HarnessExecutionSummary;
  swarmSteps?: SwarmStepResult[];
  lessonsSnippet?: string;
}): void {
  // Limpar tela do terminal para efeito de Dashboard TUI Interativo
  process.stdout.write("\x1Bc");

  const border = chalk.bold.blue("╔" + "═".repeat(68) + "╗");
  const bottomBorder = chalk.bold.blue("╚" + "═".repeat(68) + "╝");

  console.log(border);
  console.log(chalk.bold.blue("║") + chalk.bold.cyan(" 🚀 LOOPFORGE ENTERPRISE TUI DASHBOARD v2.0").padEnd(76) + chalk.bold.blue("║"));
  console.log(chalk.bold.blue("╠" + "═".repeat(68) + "╣"));

  const modelBadge = options.isFallback
    ? chalk.bgRed.white.bold(" MODEL FALLBACK: ACTIVATED ")
    : chalk.bgGreen.black.bold(" OPENCODE DEEPSEEK FREE ");

  console.log(chalk.bold.blue("║") + ` Iteração: #${options.iteration} | Estratégia: ${options.strategy.toUpperCase()} | ${modelBadge}`.padEnd(81) + chalk.bold.blue("║"));
  console.log(chalk.bold.blue("║") + ` Modelo Ativo: ${chalk.bold(options.activeModel)}`.padEnd(76) + chalk.bold.blue("║"));

  if (options.swarmSteps && options.swarmSteps.length > 0) {
    console.log(chalk.bold.blue("╠" + "─".repeat(68) + "╣"));
    console.log(chalk.bold.blue("║") + chalk.bold.yellow(" 🤖 PIPELINE SWARM MULTI-AGENTE:").padEnd(75) + chalk.bold.blue("║"));
    for (const step of options.swarmSteps) {
      console.log(chalk.bold.blue("║") + `   ▶ ${chalk.bold(step.roleName)} [${step.modelUsed}]`.padEnd(74) + chalk.bold.blue("║"));
    }
  }

  if (options.harnessSummary) {
    console.log(chalk.bold.blue("╠" + "─".repeat(68) + "╣"));
    const passRate = Math.round((options.harnessSummary.passedCount / options.harnessSummary.totalRunners) * 100);
    const progressBar = renderProgressBar(passRate);
    console.log(chalk.bold.blue("║") + ` 📊 SENSORES HARNESS: ${progressBar} ${passRate}%`.padEnd(76) + chalk.bold.blue("║"));

    for (const runner of options.harnessSummary.results) {
      const statusIcon = runner.passed ? chalk.green("✔ PASSOU") : chalk.red("✖ FALHOU");
      console.log(chalk.bold.blue("║") + `   - ${runner.runnerName} (${runner.type.toUpperCase()}): ${statusIcon}`.padEnd(75) + chalk.bold.blue("║"));
    }
  }

  if (options.lessonsSnippet) {
    console.log(chalk.bold.blue("╠" + "─".repeat(68) + "╣"));
    console.log(chalk.bold.blue("║") + chalk.bold.magenta(" 🧠 ÚLTIMAS LIÇÕES APRENDIDAS:").padEnd(75) + chalk.bold.blue("║"));
    console.log(chalk.bold.blue("║") + `   ${options.lessonsSnippet.slice(0, 60)}...`.padEnd(74) + chalk.bold.blue("║"));
  }

  console.log(bottomBorder);
}

function renderProgressBar(percentage: number): string {
  const totalBlocks = 15;
  const filledBlocks = Math.round((percentage / 100) * totalBlocks);
  const emptyBlocks = totalBlocks - filledBlocks;
  const bar = "█".repeat(filledBlocks) + "░".repeat(emptyBlocks);

  return percentage === 100 ? chalk.green(bar) : chalk.red(bar);
}
