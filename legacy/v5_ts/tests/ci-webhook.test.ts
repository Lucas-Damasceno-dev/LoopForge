import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { generateGitHubActionWorkflow } from "../src/ci/webhook.js";

describe("LoopForge CI Integration", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-ci-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve gerar o arquivo de workflow do GitHub Actions", async () => {
    const workflowPath = await generateGitHubActionWorkflow(tmpDir);

    const exists = await fs.stat(workflowPath).then(() => true).catch(() => false);
    expect(exists).toBe(true);
  });
});
