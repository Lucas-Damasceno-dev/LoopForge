import type { RunnerType } from "../config/schema.js";

export interface RunnerResult {
  runnerName: string;
  type: RunnerType;
  command: string;
  passed: boolean;
  exitCode: number | null;
  durationMs: number;
  stdout: string;
  stderr: string;
  errorDetails?: string;
  timedOut?: boolean;
}

export interface HarnessExecutionSummary {
  allPassed: boolean;
  passedCount: number;
  failedCount: number;
  totalRunners: number;
  totalDurationMs: number;
  results: RunnerResult[];
}
