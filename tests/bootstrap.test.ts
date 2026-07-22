import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { bootstrapHarness } from "../src/harness/bootstrap.js";

describe("LoopForge Auto-Harness Bootstrap", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-bootstrap-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve detectar stack Node.js/TypeScript e gerar suite de testes baseline", async () => {
    await fs.writeFile(path.join(tmpDir, "package.json"), "{}");

    const result = await bootstrapHarness(tmpDir);

    expect(result.stackDetected).toBe("Node.js / TypeScript");
    expect(result.runnersAdded.length).toBeGreaterThan(0);

    const testFileExists = await fs.stat(path.join(tmpDir, "tests/baseline.test.ts")).then(() => true).catch(() => false);
    expect(testFileExists).toBe(true);
  });
});
