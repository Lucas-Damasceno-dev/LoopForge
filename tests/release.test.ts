import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { generateReleaseNotes } from "../src/ci/release.js";

describe("LoopForge Semantic Release Generator", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-release-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve criar e atualizar o CHANGELOG.md", async () => {
    const changelogPath = await generateReleaseNotes("4.0.0", tmpDir);
    const content = await fs.readFile(changelogPath, "utf-8");

    expect(content).toContain("[4.0.0]");
    expect(content).toContain("# 📜 Changelog do Projeto");
  });
});
