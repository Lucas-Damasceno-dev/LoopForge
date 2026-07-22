import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { initCommand } from "../src/cli/commands/init.js";
import { PRESET_TEMPLATES } from "../src/skills/templates.js";

describe("LoopForge Preset Templates", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-template-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve existir templates pré-construídos para node-typescript, python-pytest e rust-cargo", () => {
    expect(PRESET_TEMPLATES["node-typescript"]).toBeDefined();
    expect(PRESET_TEMPLATES["python-pytest"]).toBeDefined();
    expect(PRESET_TEMPLATES["rust-cargo"]).toBeDefined();
  });

  it("deve popular as skills do template node-typescript ao usar init --template node-typescript", async () => {
    await initCommand(tmpDir, "node-typescript");

    const cleanCodeExists = await fs.stat(path.join(tmpDir, ".loopforge/skills/clean-code.md")).then(() => true).catch(() => false);
    const testingRulesExists = await fs.stat(path.join(tmpDir, ".loopforge/skills/testing-rules.md")).then(() => true).catch(() => false);

    expect(cleanCodeExists).toBe(true);
    expect(testingRulesExists).toBe(true);
  });
});
