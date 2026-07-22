#!/usr/bin/env node

import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { runCommand } from "./commands/run.js";
import { statusCommand } from "./commands/status.js";
import { bootstrapCommand } from "./commands/bootstrap.js";
import { refactorCommand } from "./commands/refactor.js";
import { uiCommand } from "./commands/ui.js";
import { generateGitHubActionWorkflow } from "../ci/webhook.js";
import chalk from "chalk";

const program = new Command();

program
  .name("loopforge")
  .description("Automated Loop Engineering Engine for AI Agents")
  .version("3.0.0");

program
  .command("init")
  .description("Inicializa a configuração do LoopForge, memórias e templates de skills no repositório")
  .argument("[directory]", "Diretório alvo para inicialização", ".")
  .option("-t, --template <template>", "Template de skills pré-construído (node-typescript, python-pytest, rust-cargo)")
  .action(async (directory: string, options: { template?: string }) => {
    await initCommand(directory, options.template);
  });

program
  .command("harness:bootstrap")
  .alias("bootstrap")
  .description("Analisa o repositório e gera automaticamente uma suíte de testes e sensores baseline")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await bootstrapCommand(directory);
  });

program
  .command("refactor")
  .description("Executa o motor de auto-refatoração e migração em lote de código com isolamento Git Sandbox")
  .argument("<rule>", "Regra ou instrução de refatoração (ex: 'converter para esm', 'migrar para react hooks')")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (rule: string, directory: string) => {
    await refactorCommand(rule, directory);
  });

program
  .command("ui")
  .description("Inicia o servidor local do Web Dashboard gráfico interativo no navegador")
  .argument("[directory]", "Diretório do projeto", ".")
  .option("-p, --port <port>", "Porta do servidor HTTP", "3000")
  .action(async (directory: string, options: { port?: string }) => {
    await uiCommand(directory, options);
  });

program
  .command("ci:setup")
  .description("Gera automaticamente o arquivo de workflow do GitHub Actions (.github/workflows/loopforge-ci.yml)")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    const workflowPath = await generateGitHubActionWorkflow(directory);
    console.log(chalk.green(`✔ GitHub Action Workflow gerado em: ${workflowPath}`));
  });

program
  .command("run")
  .description("Executa o ciclo do Loop Engine com Harness, Memória, Model Fallback e Git Sandbox")
  .argument("[directory]", "Diretório do projeto", ".")
  .option("--create-pr", "Cria automaticamente um Pull Request no GitHub ao concluir com sucesso")
  .action(async (directory: string, options: { createPr?: boolean }) => {
    await runCommand(directory, options);
  });

program
  .command("status")
  .description("Exibe o painel de status da configuração, provedores LLM, skills e memórias do LoopForge")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await statusCommand(directory);
  });

program.parse(process.argv);
