import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../../config/loader.js";
import { readMemoryFile } from "../../memory/manager.js";
import { loadActiveSkills } from "../../skills/loader.js";

export async function statusCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const config = await loadConfig(path.join(resolvedDir, ".loopforge.json"));
    const { loadedSkills } = await loadActiveSkills(config.skills, resolvedDir);
    const lessonsText = await readMemoryFile(path.join(resolvedDir, config.memory.lessonsFile), "Lições");

    console.log("\n" + chalk.bold.cyan("ℹ️ PAINEL DE STATUS DO LOOPFORGE"));
    console.log(chalk.bold.cyan("─".repeat(55)));
    console.log(` PROJETO:            ${chalk.bold(config.name)} (v${config.version})`);
    console.log(` ESTRATÉGIA:         ${chalk.bold.yellow(config.strategy.toUpperCase())}`);
    console.log(` PROVEDOR LLM:       ${chalk.bold.green(config.provider.name.toUpperCase())} (${config.provider.model}) [OpenCode DeepSeek Default]`);
    console.log(` MODEL FALLBACK:     ${config.provider.enableModelFallback ? chalk.cyan(config.provider.fallbackModel) + ` (após ${config.provider.fallbackFailureThreshold} falhas)` : chalk.gray("Desativado")}`);
    console.log(` GIT SANDBOX:        ${config.sandbox.enableBranchSandbox ? chalk.green(`Ativado (${config.sandbox.branchPrefix}*)`) : chalk.gray("Desativado")}`);
    console.log(` RUNNERS HARNESS:    ${chalk.bold(config.harness.runners.length)} configurados (${config.harness.runners.map((r) => r.type).join(", ")})`);
    console.log(` SKILLS ATIVAS:      ${chalk.bold(loadedSkills.length)} carregadas`);
    console.log(` CIRCUIT BREAKER:    Max ${config.guardrails.maxIterations} iterações, max ${config.guardrails.maxConsecutiveFailures} falha(s) consecutivas`);
    console.log(` ARQUIVO DE MEMÓRIA: ${config.memory.lessonsFile}`);

    const hasLessons = !lessonsText.includes("*Nenhum registro ainda.*");
    console.log(` STATUS DA MEMÓRIA:  ${hasLessons ? chalk.green("Com aprendizados registrados") : chalk.gray("Sem registros")}`);
    console.log(chalk.bold.cyan("─".repeat(55)) + "\n");
  } catch (error: any) {
    console.error(chalk.red(`❌ Erro ao ler status: ${error.message}`));
    process.exit(1);
  }
}
