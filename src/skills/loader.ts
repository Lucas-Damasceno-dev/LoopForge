import * as fs from "node:fs/promises";
import * as path from "node:path";
import type { Skill, SkillLoadResult } from "./types.js";

export async function loadActiveSkills(
  config?: { directory?: string; activeSkills?: string[] },
  baseDir: string = "."
): Promise<SkillLoadResult> {
  const directory = config?.directory || ".loopforge/skills";
  const activeSkills = config?.activeSkills || [];

  const skillDir = path.resolve(baseDir, directory);
  const loadedSkills: Skill[] = [];
  const missingSkills: string[] = [];

  try {
    await fs.mkdir(skillDir, { recursive: true });
  } catch {
    // Directory creation handled or already exists
  }

  for (const skillName of activeSkills) {
    const fileName = skillName.endsWith(".md") ? skillName : `${skillName}.md`;
    const fullPath = path.join(skillDir, fileName);

    try {
      const content = await fs.readFile(fullPath, "utf-8");
      loadedSkills.push({
        name: skillName,
        content,
        filePath: fullPath,
      });
    } catch {
      missingSkills.push(skillName);
    }
  }

  return { loadedSkills, missingSkills };
}

export function formatSkillsPrompt(skills: Skill[]): string {
  if (skills.length === 0) return "";

  const formatted = skills
    .map(
      (skill) =>
        `### 🎯 Skill: ${skill.name}\n\`\`\`markdown\n${skill.content.trim()}\n\`\`\``
    )
    .join("\n\n");

  return `## 💡 Skills e Diretrizes Especialistas Ativas\n\n${formatted}`;
}
