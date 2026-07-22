#!/usr/bin/env node

import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { runCommand } from "./commands/run.js";
import { statusCommand } from "./commands/status.js";

const program = new Command();

program
  .name("loopforge")
  .description("Automated Loop Engineering Engine for AI Agents")
  .version("0.1.0");

program
  .command("init")
  .description("Inicializa a configuração do LoopForge e a estrutura de memórias e skills no repositório")
  .argument("[directory]", "Diretório alvo para inicialização", ".")
  .action(async (directory: string) => {
    await initCommand(directory);
  });

program
  .command("run")
  .description("Executa o ciclo do Loop Engine com Harness, Memória e Safety Guardrails")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await runCommand(directory);
  });

program
  .command("status")
  .description("Exibe o painel de status da configuração, skills e memórias do LoopForge")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await statusCommand(directory);
  });

program.parse(process.argv);
