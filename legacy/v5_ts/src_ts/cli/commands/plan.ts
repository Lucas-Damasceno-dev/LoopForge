import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as readline from "node:readline/promises";
import chalk from "chalk";
import { loadConfig, createDefaultConfig } from "../../config/loader.js";
import { LLMEngine } from "../../llm/provider.js";
import { runCommand } from "./run.js";

export async function interactivePlanHelper(
  targetDir: string = "."
): Promise<boolean> {
  const resolvedDir = path.resolve(targetDir);

  console.log(chalk.bold.magenta(`\n🗺️ INTERACTIVE ROADMAP PLANNER DO LOOPFORGE`));
  console.log(chalk.gray(`Planejador conversacional via OpenCode (DeepSeek v4 Flash Free)\n`));

  let config;
  try {
    config = await loadConfig(undefined, resolvedDir);
  } catch {
    console.log(chalk.yellow(`ℹ️ Arquivo de configuração não encontrado. Inicializando padrão...`));
    await createDefaultConfig(resolvedDir);
    config = await loadConfig(undefined, resolvedDir);
  }

  const llmEngine = new LLMEngine(config.llm);
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

  try {
    const initialIdea = await rl.question(
      chalk.bold.cyan("💬 O que você deseja construir ou adicionar ao seu projeto? ")
    );

    if (!initialIdea || !initialIdea.trim()) {
      console.log(chalk.yellow("⚠️ Nenhuma ideia informada. Pulando criação interativa de roadmap."));
      rl.close();
      return false;
    }

    console.log(chalk.cyan(`\n🤖 Analisando projeto com a IA e elaborando perguntas de alinhamento...\n`));

    const conversationHistory = [
      `Idéia inicial do projeto enviada pelo usuário: "${initialIdea.trim()}"`,
    ];

    let rounds = 0;
    const maxRounds = 3;
    let isOffline = false;

    const defaultQuestions = [
      `Pergunta de Alinhamento #1 - Escopo do Projeto:
Qual o tipo de aplicação que você deseja construir?

1) Web App (interface com usuário via navegador)
2) API / REST (backend para servir dados)
3) CLI / Ferramenta de terminal
4) Biblioteca / Pacote reutilizável
5) Mobile / Aplicativo híbrido`,

      `Pergunta de Alinhamento #2 - Stack Tecnológica:
Qual stack tecnológica você prefere para este projeto?

1) TypeScript + React / Next.js (web moderno)
2) Python + FastAPI / Django (backend robusto)
3) TypeScript + Node / Express (API rápida)
4) Go / Rust (alta performance)
5) Indeciso — sugestão do arquiteto`,

      `Pergunta de Alinhamento #3 - Complexidade e Prazos:
Qual o nível de complexidade esperado para o projeto?

1) Protótipo simples (funcionalidade básica, poucos dias)
2) MVP funcional (mínimo produto viável, 1-2 semanas)
3) Aplicação completa (com autenticação, banco, testes)
4) Sistema distribuído (múltiplos serviços, escalabilidade)
5) Plataforma multi-tenant (saas, múltiplos usuários)`,
    ];

    while (rounds < maxRounds) {
      rounds++;

      const promptContext = `
Você é o Arquiteto de Software do LoopForge.
O usuário quer planejar o seguinte projeto/funcionalidade:
${conversationHistory.join("\n")}

Gere a Pergunta de Alinhamento #${rounds} para definir o escopo e a arquitetura.
REGRAS OBRIGATÓRIAS:
1. Faça 1 pergunta clara sobre arquitetura, banco, autenticação, UI ou stack.
2. Forneça exatamente 5 opções numéricas de resposta (1, 2, 3, 4, 5) com justificativas curtas para ajudar a decisão do usuário.
3. Mantenha o texto objetivo e em Português.
`;

      const aiResponse = await llmEngine.generateStep(promptContext);
      console.log(chalk.bold.yellow(`\n[Pergunta ${rounds}/${maxRounds}]`));

      let questionContent: string;
      if (aiResponse.isFallback) {
        if (!isOffline) {
          console.log(chalk.yellow(`\n⚠️  Servidor OpenCode indisponível. Usando perguntas padrão.\n`));
        }
        isOffline = true;
        questionContent = defaultQuestions[rounds - 1];
      } else {
        questionContent = aiResponse.content.trim();
      }
      console.log(chalk.white(questionContent));

      const answer = await rl.question(
        chalk.bold.green(`\n👉 Escolha uma opção (1-5) ou digite sua resposta (ou 'ok' para concluir): `)
      );

      if (answer.trim().toLowerCase() === "ok") {
        break;
      }

      conversationHistory.push(`Pergunta da IA #${rounds}: ${questionContent}`);
      conversationHistory.push(`Resposta do usuário #${rounds}: ${answer.trim()}`);
    }

    console.log(chalk.cyan(`\n⚡ Sintetizando Roadmap e preenchendo governança do LoopForge...\n`));

    let roadmapText: string;
    let handoffText: string;

    if (isOffline) {
      // Modo offline: gera roadmap padrão baseado nas respostas do usuário
      roadmapText = `# 🗺️ Roadmap de Desenvolvimento

## Fase 1: Fundação & Protótipo
- Configurar estrutura do projeto e tooling
- Implementar funcionalidade principal
- Criar testes unitários iniciais

## Fase 2: Expansão
- Adicionar autenticação e autorização
- Implementar banco de dados e persistência
- Expandir cobertura de testes

## Fase 3: Polimento & Deploy
- Refinar UI/UX
- Otimizar performance
- Configurar CI/CD e deploy
`;
      handoffText = `# 🤝 Estado do Projeto & Próximo Passo

- **Passo Atual**: Planejamento concluído (modo offline)
- **Ideia Inicial**: ${initialIdea.trim()}
- **Próximo Objetivo**: Executar Fase 1 do Roadmap
- **Stack**: A definir com base nas respostas do planejamento
`;
    } else {
      const finalPlanPrompt = `
Com base na conversação completa:
${conversationHistory.join("\n")}

Crie a especificação final do Roadmap dividida em fases testáveis.
Responda EXATAMENTE no formato JSON com as chaves:
{
  "roadmapMarkdown": "# 🗺️ Roadmap de Desenvolvimento\\n...",
  "handoffMarkdown": "# 🤝 Estado do Projeto & Próximo Passo\\n..."
}
`;

      const planAiResponse = await llmEngine.generateStep(finalPlanPrompt);

      roadmapText = `# 🗺️ Roadmap de Desenvolvimento\n\n## Fase 1: Fundação & Protótipo\n- Implementar estrutura base\n- Criar testes iniciais\n`;
      handoffText = `# 🤝 Estado do Projeto & Próximo Passo\n\n- **Passo Atual**: Inicialização\n- **Próximo Objetivo**: Executar Fase 1 do Roadmap\n`;

      try {
        const jsonMatch = planAiResponse.content.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const parsed = JSON.parse(jsonMatch[0]);
          if (parsed.roadmapMarkdown) roadmapText = parsed.roadmapMarkdown;
          if (parsed.handoffMarkdown) handoffText = parsed.handoffMarkdown;
        }
      } catch {
        // Fallback
      }
    }

    const skillsDir = path.resolve(resolvedDir, ".loopforge/skills");
    const roadmapPath = path.join(skillsDir, "roadmap.md");
    const handoffPath = path.resolve(resolvedDir, ".loopforge/handoff.md");

    await fs.mkdir(skillsDir, { recursive: true });
    await fs.writeFile(roadmapPath, roadmapText, "utf-8");
    await fs.writeFile(handoffPath, handoffText, "utf-8");

    console.log(chalk.bold.green(`✔ Roadmap gerado com sucesso em: ${roadmapPath}`));
    console.log(chalk.bold.green(`✔ Handoff atualizado com sucesso em: ${handoffPath}`));

    rl.close();
    return true;
  } catch (error) {
    rl.close();
    const msg = error instanceof Error ? error.message : String(error);
    console.error(chalk.red(`❌ Erro no planejador interativo: ${msg}`));
    return false;
  }
}

export async function planCommand(targetDir: string = "."): Promise<void> {
  const success = await interactivePlanHelper(targetDir);
  if (success) {
    console.log(chalk.bold.magenta(`\n🔄 Iniciando o LoopForge Engine autônomo...`));
    await runCommand(targetDir, { skipPlan: true });
  }
}
