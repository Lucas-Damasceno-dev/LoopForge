#!/usr/bin/env node

import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { runCommand } from "./commands/run.js";
import { statusCommand } from "./commands/status.js";
import { bootstrapCommand } from "./commands/bootstrap.js";
import { refactorCommand } from "./commands/refactor.js";
import { uiCommand } from "./commands/ui.js";
import { workspaceCommand } from "./commands/workspace.js";
import { auditCommand } from "./commands/audit.js";
import { wizardCommand } from "./commands/wizard.js";
import { replayCommand } from "./commands/replay.js";
import { generateTestsCommand } from "./commands/generate-tests.js";
import { releaseCommand } from "./commands/release.js";
import { dockerRunCommand } from "./commands/docker.js";
import { analyticsCommand } from "./commands/analytics.js";
import { generateGitHubActionWorkflow } from "../ci/webhook.js";
import chalk from "chalk";

const program = new Command();

program
  .name("loopforge")
  .description("Automated Loop Engineering Engine for AI Agents")
  .version("5.0.0");

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
  .command("generate-tests")
  .description("Gera autonomamente suítes de testes unitários para arquivos de código não cobertos")
  .argument("[directory]", "Diretório do projeto", ".")
  .option("--dry-run", "Simula a criação de testes exibindo a lista e o diff sem gravar arquivos")
  .action(async (directory: string, options: { dryRun?: boolean }) => {
    await generateTestsCommand(directory, options);
  });

program
  .command("docker")
  .description("Executa comandos no Docker Container Sandbox isolado")
  .argument("<cmd>", "Comando a ser executado dentro do container")
  .option("-i, --image <image>", "Imagem Docker", "node:20-alpine")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (cmd: string, options: { image?: string }, directory: string) => {
    await dockerRunCommand(cmd, options.image, directory);
  });

program
  .command("analytics")
  .description("Compila métricas de telemetria e gera relatório gráfico visual HTML")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await analyticsCommand(directory);
  });

program
  .command("release")
  .description("Gera notas de lançamento semânticas e atualiza o arquivo CHANGELOG.md")
  .argument("[version]", "Versão da release", "5.0.0")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (version: string, directory: string) => {
    await releaseCommand(version, directory);
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
  .description("Inicia o servidor local do Web Dashboard gráfico interativo com WebSocket no navegador")
  .argument("[directory]", "Diretório do projeto", ".")
  .option("-p, --port <port>", "Porta do servidor HTTP", "3000")
  .action(async (directory: string, options: { port?: string }) => {
    await uiCommand(directory, options);
  });

program
  .command("workspace")
  .description("Orquestra execuções de loops em múltiplos repositórios do workspace em lote")
  .argument("[workspaceFile]", "Arquivo manifesto de workspace", "loopforge-workspace.json")
  .argument("[directory]", "Diretório raiz", ".")
  .action(async (workspaceFile: string, directory: string) => {
    await workspaceCommand(workspaceFile, directory);
  });

program
  .command("audit")
  .description("Executa o scanner de segurança e code smells em busca de segredos expostos e falhas OWASP")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await auditCommand(directory);
  });

program
  .command("wizard")
  .description("Assistente guiado interativo de onboarding e configuração do LoopForge")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (directory: string) => {
    await wizardCommand(directory);
  });

program
  .command("replay")
  .description("Reproduz em tempo real a gravação de telemetria de uma sessão passada")
  .argument("<sessionId>", "ID da sessão gravada em .loopforge/telemetry/")
  .argument("[directory]", "Diretório do projeto", ".")
  .action(async (sessionId: string, directory: string) => {
    await replayCommand(sessionId, directory);
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
  .option("-w, --watch", "Re-executa o ciclo automaticamente sempre que arquivos .ts forem alterados")
  .action(async (directory: string, options: { createPr?: boolean; watch?: boolean }) => {
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
