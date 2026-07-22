import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { createDefaultConfig } from "../../config/loader.js";

export async function initCommand(targetDir: string = "."): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const configPath = await createDefaultConfig(resolvedDir);
    const skillsDir = path.resolve(resolvedDir, ".loopforge/skills");
    const lessonsFile = path.resolve(resolvedDir, ".loopforge/lessons.md");
    const handoffFile = path.resolve(resolvedDir, ".loopforge/handoff.md");

    await fs.mkdir(skillsDir, { recursive: true });

    // Criar arquivo de exemplo de Skill
    const sampleSkillPath = path.join(skillsDir, "quality-rules.md");
    const sampleSkillContent = `# Diretrizes de Qualidade
- Mantenha funções pequenas e com responsabilidade única.
- Cubra novos métodos com testes unitários.
- Não remova ou ignore falhas de linter ou compilador.
`;
    await fs.writeFile(sampleSkillPath, sampleSkillContent, "utf-8");

    // Criar arquivos iniciais de memória se não existirem
    await fs.writeFile(
      lessonsFile,
      "# 🧠 Lições Aprendidas (Lessons Learned)\n\n*Nenhuma lição registrada ainda.*\n",
      { flag: "wx" }
    ).catch(() => {});

    await fs.writeFile(
      handoffFile,
      "# 🤝 Instruções de Transição (Handoff)\n\n*Aguardando primeira iteração do loop.*\n",
      { flag: "wx" }
    ).catch(() => {});

    console.log(chalk.green("✔ Projeto LoopForge inicializado com sucesso!"));
    console.log(chalk.cyan(`  Configuração: ${configPath}`));
    console.log(chalk.cyan(`  Diretório de Skills: ${skillsDir}`));
    console.log(chalk.cyan(`  Memória Lessons: ${lessonsFile}`));
    console.log(chalk.cyan(`  Memória Handoff: ${handoffFile}`));
  } catch (error: any) {
    console.error(chalk.red(`❌ Falha ao inicializar o LoopForge: ${error.message}`));
    process.exit(1);
  }
}
