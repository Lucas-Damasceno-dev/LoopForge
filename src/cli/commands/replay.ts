import * as path from "node:path";
import chalk from "chalk";
import { TelemetryRecorder } from "../../telemetry/recorder.js";

export async function replayCommand(sessionId: string, targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    console.log(chalk.cyan(`🎬 Iniciando Reprodução de Sessão (Live Replay): ${sessionId}...`));
    const frames = await TelemetryRecorder.loadReplaySession(sessionId, resolvedDir);

    for (const frame of frames) {
      console.log(
        chalk.gray(`[${frame.timestamp}]`) +
          ` | Iteração ${frame.iteration} | Papel: ${chalk.yellow(frame.role)} | Modelo: ${chalk.blue(frame.model)} | Harness: ${
            frame.harnessPassed ? chalk.green("PASS") : chalk.red("FAIL")
          }`
      );
      await new Promise((res) => setTimeout(res, 300));
    }

    console.log(chalk.green(`\n✔ Replay encerrado com sucesso!`));
  } catch (err: any) {
    console.error(chalk.red(`❌ Erro ao reproduzir sessão: ${err.message}`));
  }
}
