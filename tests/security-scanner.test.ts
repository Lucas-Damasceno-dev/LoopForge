import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { SecurityScanner } from "../src/guardrails/security-scanner.js";

describe("LoopForge Security Scanner", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-sec-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve detectar chaves de API expostas no código", async () => {
    const filePath = path.join(tmpDir, "config.js");
    await fs.writeFile(filePath, 'const apiKey = "sk-12345678901234567890123456789012";', "utf-8");

    const scanner = new SecurityScanner();
    const vulns = await scanner.scanDirectory(tmpDir);

    expect(vulns.length).toBeGreaterThan(0);
    expect(vulns[0].type).toBe("hardcoded_secret");
  });
});
