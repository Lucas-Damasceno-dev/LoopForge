import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface TelemetryFrame {
  timestamp: string;
  iteration: number;
  role: string;
  model: string;
  isFallback: boolean;
  harnessPassed: boolean;
}

export class TelemetryRecorder {
  private sessionDir: string;
  private sessionId: string;
  private frames: TelemetryFrame[] = [];

  constructor(sessionId?: string, cwd: string = ".") {
    this.sessionId = sessionId || `session-${Date.now()}`;
    this.sessionDir = path.resolve(cwd, ".loopforge/telemetry");
  }

  public async recordFrame(frame: Omit<TelemetryFrame, "timestamp">): Promise<void> {
    await fs.mkdir(this.sessionDir, { recursive: true });
    const fullFrame: TelemetryFrame = {
      ...frame,
      timestamp: new Date().toISOString(),
    };
    this.frames.push(fullFrame);
    const filePath = path.join(this.sessionDir, `${this.sessionId}.json`);
    await fs.writeFile(filePath, JSON.stringify(this.frames, null, 2), "utf-8");
  }

  public static async loadReplaySession(sessionId: string, cwd: string = "."): Promise<TelemetryFrame[]> {
    const filePath = path.resolve(cwd, `.loopforge/telemetry/${sessionId}.json`);
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw);
  }
}
