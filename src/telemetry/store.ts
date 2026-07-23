import * as path from "node:path";
import * as fs from "node:fs/promises";
import Database from "better-sqlite3";

export interface SessionRecord {
  id?: number;
  projectName: string;
  timestamp: string;
  totalIterations: number;
  totalTokensUsed: number;
  totalCostUsd: number;
  success: boolean;
  stopReason: string;
}

export interface IterationRecord {
  id?: number;
  sessionId: number;
  iteration: number;
  passed: boolean;
  modelUsed: string;
  tokensUsed: number;
  costUsd: number;
}

export class TelemetryStore {
  private db: Database.Database;

  constructor(dbPath: string) {
    this.db = new Database(dbPath);
    this.initTables();
  }

  public static async getInstance(cwd: string = "."): Promise<TelemetryStore> {
    const resolvedDir = path.resolve(cwd);
    const telemetryDir = path.join(resolvedDir, ".loopforge");
    await fs.mkdir(telemetryDir, { recursive: true });
    const dbPath = path.join(telemetryDir, "telemetry.sqlite");
    return new TelemetryStore(dbPath);
  }

  private initTables(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        total_iterations INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        total_cost_usd REAL NOT NULL,
        success INTEGER NOT NULL,
        stop_reason TEXT
      );

      CREATE TABLE IF NOT EXISTS iterations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        iteration_number INTEGER NOT NULL,
        passed INTEGER NOT NULL,
        model_used TEXT NOT NULL,
        tokens_used INTEGER NOT NULL,
        cost_usd REAL NOT NULL,
        FOREIGN KEY(session_id) REFERENCES sessions(id)
      );
    `);
  }

  public recordSession(session: SessionRecord, iterations: Omit<IterationRecord, "sessionId">[] = []): number {
    const stmt = this.db.prepare(`
      INSERT INTO sessions (project_name, timestamp, total_iterations, total_tokens, total_cost_usd, success, stop_reason)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `);

    const result = stmt.run(
      session.projectName,
      session.timestamp || new Date().toISOString(),
      session.totalIterations,
      session.totalTokensUsed,
      session.totalCostUsd,
      session.success ? 1 : 0,
      session.stopReason
    );

    const sessionId = Number(result.lastInsertRowid);

    const iterStmt = this.db.prepare(`
      INSERT INTO iterations (session_id, iteration_number, passed, model_used, tokens_used, cost_usd)
      VALUES (?, ?, ?, ?, ?, ?)
    `);

    for (const iter of iterations) {
      iterStmt.run(sessionId, iter.iteration, iter.passed ? 1 : 0, iter.modelUsed, iter.tokensUsed, iter.costUsd);
    }

    return sessionId;
  }

  public getAllSessions(): SessionRecord[] {
    const rows = this.db.prepare("SELECT * FROM sessions ORDER BY id DESC").all() as any[];
    return rows.map((r) => ({
      id: r.id,
      projectName: r.project_name,
      timestamp: r.timestamp,
      totalIterations: r.total_iterations,
      totalTokensUsed: r.total_tokens,
      totalCostUsd: r.total_cost_usd,
      success: r.success === 1,
      stopReason: r.stop_reason,
    }));
  }

  public getCostTrend(): { timestamp: string; costUsd: number }[] {
    const rows = this.db.prepare("SELECT timestamp, total_cost_usd FROM sessions ORDER BY id ASC").all() as any[];
    return rows.map((r) => ({ timestamp: r.timestamp, costUsd: r.total_cost_usd }));
  }

  public getPassRateTrend(): { timestamp: string; passRate: number }[] {
    const rows = this.db.prepare(`
      SELECT s.timestamp,
        ROUND(AVG(i.passed) * 100, 2) as passRate
      FROM sessions s
      JOIN iterations i ON i.session_id = s.id
      GROUP BY s.id
      ORDER BY s.id ASC
    `).all() as any[];
    return rows.map((r) => ({ timestamp: r.timestamp, passRate: r.passRate || 0 }));
  }

  public close(): void {
    this.db.close();
  }
}
