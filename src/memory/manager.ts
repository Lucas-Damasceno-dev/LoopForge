import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface MemoryState {
  lessons: string;
  handoff: string;
}

export async function readMemoryFile(filePath: string, defaultTitle: string): Promise<string> {
  try {
    const resolved = path.resolve(filePath);
    return await fs.readFile(resolved, "utf-8");
  } catch {
    return `# ${defaultTitle}\n\n*Nenhum registro ainda.*\n`;
  }
}

export async function appendLesson(filePath: string, lesson: string): Promise<void> {
  const resolved = path.resolve(filePath);
  const existing = await readMemoryFile(filePath, "🧠 Lições Aprendidas (Lessons Learned)");

  const timestamp = new Date().toISOString();
  const entry = `\n- **[${timestamp}]**: ${lesson.trim()}\n`;

  const updated = existing.includes("*Nenhum registro ainda.*")
    ? existing.replace("*Nenhum registro ainda.*", entry.trimStart())
    : `${existing.trimEnd()}\n${entry}`;

  await fs.mkdir(path.dirname(resolved), { recursive: true });
  await fs.writeFile(resolved, updated, "utf-8");
}

export async function updateHandoff(filePath: string, handoffContent: string): Promise<void> {
  const resolved = path.resolve(filePath);
  await fs.mkdir(path.dirname(resolved), { recursive: true });
  await fs.writeFile(resolved, handoffContent, "utf-8");
}

export function formatMemoryPrompt(lessons: string, handoff: string): string {
  return `## 🧠 Memória Persistente do Repositório

### 📚 Lições Aprendidas (Lessons Learned):
\`\`\`markdown
${lessons.trim()}
\`\`\`

### 🤝 Handoff e Instruções de Transição:
\`\`\`markdown
${handoff.trim()}
\`\`\``;
}
