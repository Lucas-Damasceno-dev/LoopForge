import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { createDefaultConfig } from "../../config/loader.js";
import { PRESET_TEMPLATES } from "../../skills/templates.js";

export async function initCommand(targetDir: string = ".", templateName?: string): Promise<void> {
  const resolvedDir = path.resolve(targetDir);

  try {
    const configPath = await createDefaultConfig(resolvedDir);
    const skillsDir = path.resolve(resolvedDir, ".loopforge/skills");
    const lessonsFile = path.resolve(resolvedDir, ".loopforge/lessons.md");
    const handoffFile = path.resolve(resolvedDir, ".loopforge/handoff.md");

    await fs.mkdir(skillsDir, { recursive: true });

    let appliedTemplate = "default";

    if (templateName && PRESET_TEMPLATES[templateName]) {
      const template = PRESET_TEMPLATES[templateName];
      appliedTemplate = template.name;

      for (const [filename, content] of Object.entries(template.skills)) {
        await fs.writeFile(path.join(skillsDir, filename), content, "utf-8");
      }
    } else {
      // Skill padrão de amostra
      const sampleSkillPath = path.join(skillsDir, "quality-rules.md");
      const sampleSkillContent = `# Diretrizes de Qualidade
- Mantenha funções pequenas e com responsabilidade única.
- Cubra novos métodos com testes unitários.
- Não remova ou ignore falhas de linter ou compilador.
`;
      await fs.writeFile(sampleSkillPath, sampleSkillContent, "utf-8");
    }

    // Criar arquivos iniciais de memória se não existirem
    try {
      await fs.writeFile(
        lessonsFile,
        "# 🧠 Lições Aprendidas (Lessons Learned)\n\n*Nenhuma lição registrada ainda.*\n",
        { flag: "wx" }
      );
    } catch {
      // File already exists
    }

    try {
      await fs.writeFile(
        handoffFile,
        "# 🤝 Instruções de Transição (Handoff)\n\n*Aguardando primeira iteração do loop.*\n",
        { flag: "wx" }
      );
    } catch {
      // File already exists
    }

    console.log(chalk.green("✔ Projeto LoopForge inicializado com sucesso!"));
    console.log(chalk.cyan(`  Template Aplicado: ${appliedTemplate}`));
    console.log(chalk.cyan(`  Configuração: ${configPath}`));
    console.log(chalk.cyan(`  Provedor Padrão: OpenCode (DeepSeek v4 free)`));
    console.log(chalk.cyan(`  Diretório de Skills: ${skillsDir}`));
    console.log(chalk.cyan(`  Memória Lessons: ${lessonsFile}`));
    console.log(chalk.cyan(`  Memória Handoff: ${handoffFile}`));
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    console.error(chalk.red(`❌ Falha ao inicializar o LoopForge: ${msg}`));
    process.exit(1);
  }
}
