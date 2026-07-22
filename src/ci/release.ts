import * as fs from "node:fs/promises";
import * as path from "node:path";
import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

export async function generateReleaseNotes(version: string = "3.1.0", cwd: string = "."): Promise<string> {
  const resolvedDir = path.resolve(cwd);
  const changelogPath = path.join(resolvedDir, "CHANGELOG.md");

  let gitLogs = "Refatorações e melhorias de automação via LoopForge.";
  try {
    const { stdout } = await execAsync("git log -n 5 --oneline", { cwd: resolvedDir });
    if (stdout.trim()) gitLogs = stdout.trim();
  } catch {}

  const date = new Date().toISOString().split("T")[0];
  const newEntry = `## [${version}] - ${date}\n\n### 🚀 Alterações Automatizadas:\n\`\`\`text\n${gitLogs}\n\`\`\`\n\n`;

  let existing = "";
  try {
    existing = await fs.readFile(changelogPath, "utf-8");
  } catch {
    existing = "# 📜 Changelog do Projeto\n\n";
  }

  const updatedChangelog = existing.includes("# 📜 Changelog do Projeto\n\n")
    ? existing.replace("# 📜 Changelog do Projeto\n\n", `# 📜 Changelog do Projeto\n\n${newEntry}`)
    : `${newEntry}${existing}`;

  await fs.writeFile(changelogPath, updatedChangelog, "utf-8");
  return changelogPath;
}
