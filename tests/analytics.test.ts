import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { generateAnalyticsReport } from "../src/telemetry/analytics.js";

describe("LoopForge Telemetry Analytics", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-analytics-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve compilar estatísticas e gerar relatório HTML de analytics", async () => {
    const { summary, reportHtmlPath } = await generateAnalyticsReport(tmpDir);

    expect(summary.totalSessions).toBe(1);
    const content = await fs.readFile(reportHtmlPath, "utf-8");
    expect(content).toContain("Relatório de Telemetria");
  });
});
