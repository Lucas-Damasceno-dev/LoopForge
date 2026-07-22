import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { initCommand } from "../src/cli/commands/init.js";

describe("LoopForge CLI Commands", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-cli-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve inicializar a estrutura completa de pastas e arquivos no diretório temporário", async () => {
    await initCommand(tmpDir);

    const configExists = await fs.stat(path.join(tmpDir, ".loopforge.json")).then(() => true).catch(() => false);
    const skillExists = await fs.stat(path.join(tmpDir, ".loopforge/skills/quality-rules.md")).then(() => true).catch(() => false);
    const lessonsExists = await fs.stat(path.join(tmpDir, ".loopforge/lessons.md")).then(() => true).catch(() => false);
    const handoffExists = await fs.stat(path.join(tmpDir, ".loopforge/handoff.md")).then(() => true).catch(() => false);

    expect(configExists).toBe(true);
    expect(skillExists).toBe(true);
    expect(lessonsExists).toBe(true);
    expect(handoffExists).toBe(true);
  });
});
