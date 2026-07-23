import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";

export async function statusCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const config = await loadConfig(path.join(resolvedDir, ".loopforge.json"));

    console.log("\n" + chalk.bold.cyan("ℹ️ PAINEL DE STATUS DO LOOPFORGE v5.0"));
    console.log(chalk.bold.cyan("─".repeat(55)));
    console.log(` PROJETO:            ${chalk.bold(config.projectName)} (v${config.version})`);
    console.log(` PROVEDOR LLM:       ${chalk.bold.green((config.llm?.provider || "opencode").toUpperCase())} (${config.llm?.model})`);
    console.log(` MODEL FALLBACK:     ${chalk.cyan(config.llm?.fallbackModel)}`);
    console.log(` RUNNERS HARNESS:    ${chalk.bold(config.harness.runners.length)} configurados (${config.harness.runners.map((r) => r.type).join(", ")})`);
    console.log(` PARALELISMO HARNESS:${config.harness.parallel ? chalk.green("Ativado (Promise.all)") : chalk.gray("Sequencial")}`);
    console.log(` CIRCUIT BREAKER:    Max ${config.guardrails?.maxTotalIterations} iterações, max ${config.guardrails?.maxConsecutiveFailures} falhas, Teto: $${config.guardrails?.maxBudgetUsd}`);
    console.log(chalk.bold.cyan("─".repeat(55)) + "\n");
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(chalk.red(`❌ Erro ao ler status: ${msg}`));
    process.exit(1);
  }
}
