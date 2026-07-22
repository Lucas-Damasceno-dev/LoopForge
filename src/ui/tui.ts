import chalk from "chalk";

export interface TUIDashboardState {
  iteration: number;
  currentRole: string;
  activeModel: string;
  isFallback: boolean;
  passRatePercent: number;
  tokensUsed: number;
  costUsd: number;
  lastLesson: string;
  streamingChunk?: string;
}

export function renderTUIDashboard(state: TUIDashboardState): void {
  console.clear();

  const border = chalk.cyan("═".repeat(65));
  const modelBadge = state.isFallback
    ? chalk.bgRed.white.bold(` FALLBACK: ${state.activeModel} `)
    : chalk.bgGreen.black.bold(` OPENCODE: ${state.activeModel} `);

  const progressBar = renderProgressBar(state.passRatePercent);

  console.log(border);
  console.log(chalk.bold.magenta(`  🚀 LOOPFORGE INTERACTIVE TUI DASHBOARD  `) + modelBadge);
  console.log(border);
  console.log(`  Iteração Atual: ${chalk.bold.yellow(`#${state.iteration}`)} | Papel Swarm: ${chalk.bold.cyan(state.currentRole.toUpperCase())}`);
  console.log(`  Sensor Pass-Rate: [${progressBar}] ${chalk.bold(`${state.passRatePercent}%`)}`);
  console.log(`  Consumo: ${chalk.bold(`${state.tokensUsed} tokens`)} | Custo Est.: ${chalk.bold.green(`$${state.costUsd.toFixed(4)}`)}`);
  console.log(chalk.cyan("─".repeat(65)));

  if (state.streamingChunk) {
    console.log(chalk.bold.white(`  🌊 Live Stream:`) + ` ${chalk.gray(state.streamingChunk.slice(-150))}`);
    console.log(chalk.cyan("─".repeat(65)));
  }

  console.log(`  🧠 Última Lição Aprendida: ${chalk.italic.gray(state.lastLesson || "Nenhuma falha recente")}`);
  console.log(border + "\n");
}

function renderProgressBar(percent: number, width: number = 25): string {
  const filled = Math.round((percent / 100) * width);
  const empty = width - filled;
  return chalk.green("█".repeat(filled)) + chalk.gray("░".repeat(empty));
}
