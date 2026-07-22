import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { loadActiveSkills, formatSkillsPrompt } from "../src/skills/loader.js";

describe("LoopForge Skills System", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-skills-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve carregar skills ativas a partir de arquivos Markdown", async () => {
    const skillsDir = path.join(tmpDir, ".loopforge/skills");
    await fs.mkdir(skillsDir, { recursive: true });

    await fs.writeFile(
      path.join(skillsDir, "clean-code.md"),
      "# Clean Code Rules\n- Evite código duplicado."
    );

    const result = await loadActiveSkills(
      { directory: ".loopforge/skills", activeSkills: ["clean-code", "non-existent"] },
      tmpDir
    );

    expect(result.loadedSkills.length).toBe(1);
    expect(result.loadedSkills[0].name).toBe("clean-code");
    expect(result.loadedSkills[0].content).toContain("Clean Code Rules");
    expect(result.missingSkills).toEqual(["non-existent"]);
  });

  it("deve formatar o bloco de prompt corretamente para as skills carregadas", () => {
    const skills = [
      {
        name: "security-rules",
        content: "- Nunca envie senhas em plain text.",
        filePath: "/tmp/security-rules.md",
      },
    ];

    const promptText = formatSkillsPrompt(skills);
    expect(promptText).toContain("## 💡 Skills e Diretrizes Especialistas Ativas");
    expect(promptText).toContain("🎯 Skill: security-rules");
    expect(promptText).toContain("- Nunca envie senhas em plain text.");
  });
});
