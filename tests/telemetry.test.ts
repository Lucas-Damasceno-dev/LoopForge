import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { TelemetryRecorder } from "../src/telemetry/recorder.js";

describe("LoopForge Telemetry Recorder", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-telem-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve gravar e recuperar quadros de telemetria de uma sessão", async () => {
    const recorder = new TelemetryRecorder("test-session", tmpDir);
    await recorder.recordFrame({
      iteration: 1,
      role: "coder",
      model: "deepseek-v3",
      isFallback: false,
      harnessPassed: true,
    });

    const frames = await TelemetryRecorder.loadReplaySession("test-session", tmpDir);
    expect(frames.length).toBe(1);
    expect(frames[0].role).toBe("coder");
  });
});
