import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { TestGenerator } from "../src/harness/test-generator.js";

describe("LoopForge Autonomous Test Generator", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-testgen-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve gerar testes unitários para arquivos sem cobertura", async () => {
    const srcDir = path.join(tmpDir, "src");
    await fs.mkdir(srcDir, { recursive: true });
    await fs.writeFile(path.join(srcDir, "auth.ts"), "export const login = () => true;");

    const generator = new TestGenerator();
    const created = await generator.generateTestsForUncoveredCode(tmpDir);

    expect(created.length).toBe(1);
    expect(created[0].testFile).toContain("auth.test.ts");
  });
});
