#!/usr/bin/env node

import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { runCommand } from "./commands/run.js";
import { statusCommand } from "./commands/status.js";

const program = new Command();

program
  .name("loopforge")
  .description("Automated Loop Engineering Engine for AI Agents")
  .version("0.2.0");

program
  .command("init")
  .description("Inicializa a configuração do LoopForge, memórias e templates de skills no repositório")
  .argument("[directory]", "Diretório alvo para inicialização", ".")
  .option("-t, --template <template>", "Template de skills pré-construído (node-typescript, python-pytest, rust-cargo)")
  .action(async (directory: string, options: { template?: string }) => {
    await initCommand(directory, options.template);
  });

program
  .command("run")
  .description("Executa o ciclo do Loop Engine com Harness, Memória, Model Fallback e Git Sandbox")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await runCommand(directory);
  });

program
  .command("status")
  .description("Exibe o painel de status da configuração, provedores LLM, skills e memórias do LoopForge")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await statusCommand(directory);
  });

program.parse(process.argv);
