import * as fs from "node:fs/promises";
import * as path from "node:path";
import { exec } from "node:child_process";
import { promisify } from "node:util";
import type { MemoryConfig } from "../config/schema.js";

const execAsync = promisify(exec);

export class MemoryManager {
  private lessonsPath: string;
  private handoffPath: string;

  constructor(config?: MemoryConfig, cwd: string = ".") {
    const lessonsFile = config?.lessonsFile || ".loopforge/lessons.md";
    const handoffFile = config?.handoffFile || ".loopforge/handoff.md";

    this.lessonsPath = path.resolve(cwd, lessonsFile);
    this.handoffPath = path.resolve(cwd, handoffFile);
  }

  public async initMemoryFiles(): Promise<void> {
    await fs.mkdir(path.dirname(this.lessonsPath), { recursive: true });
    await fs.mkdir(path.dirname(this.handoffPath), { recursive: true });

    try {
      await fs.access(this.lessonsPath);
    } catch {
      await fs.writeFile(
        this.lessonsPath,
        `# 🧠 LoopForge Lessons Learned\n\n> Lições aprendidas em falhas anteriores para prevenir loops infinitos.\n\n`,
        "utf-8"
      );
    }

    try {
      await fs.access(this.handoffPath);
    } catch {
      await fs.writeFile(
        this.handoffPath,
        `# 🔄 LoopForge State Handoff\n\n- **Status**: Inicializado\n- **Última Ação**: Aguardando execução do primeiro ciclo\n`,
        "utf-8"
      );
    }
  }

  public async appendLesson(failureMessage: string, fixApplied: string): Promise<void> {
    await this.initMemoryFiles();
    const timestamp = new Date().toISOString();
    const entry = `### [${timestamp}]\n- **Falha Encontrada**: ${failureMessage}\n- **Lição / Correção**: ${fixApplied}\n\n`;
    await fs.appendFile(this.lessonsPath, entry, "utf-8");
  }

  public async updateHandoff(stepDescription: string, nextObjective: string, cwd: string = "."): Promise<void> {
    await this.initMemoryFiles();
    const timestamp = new Date().toISOString();

    let diffStat = "Nenhuma alteração detectada no repositório.";
    try {
      const { stdout } = await execAsync("git diff --stat", { cwd });
      if (stdout.trim()) {
        diffStat = stdout.trim();
      }
    } catch {}

    const content = `# 🔄 LoopForge State Handoff\n\n` +
      `- **Última Atualização**: ${timestamp}\n` +
      `- **Passo Concluído**: ${stepDescription}\n` +
      `- **Próximo Objetivo**: ${nextObjective}\n\n` +
      `### 📊 Git Diff Stat Semântico:\n\`\`\`text\n${diffStat}\n\`\`\`\n`;

    await fs.writeFile(this.handoffPath, content, "utf-8");
  }

  public async readLessonsPrompt(): Promise<string> {
    try {
      const raw = await fs.readFile(this.lessonsPath, "utf-8");
      return raw.trim();
    } catch {
      return "Nenhuma lição aprendida ainda.";
    }
  }

  public async readHandoffPrompt(): Promise<string> {
    try {
      const raw = await fs.readFile(this.handoffPath, "utf-8");
      return raw.trim();
    } catch {
      return "Nenhum handoff de estado ativo.";
    }
  }
}
