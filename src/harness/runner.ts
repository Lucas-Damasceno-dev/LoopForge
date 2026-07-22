import { exec } from "node:child_process";
import { promisify } from "node:util";
import type { HarnessRunnerConfig } from "../config/schema.js";
import type { RunnerResult, HarnessExecutionSummary } from "./types.js";
import { parseRunnerErrors } from "./parser.js";

const execAsync = promisify(exec);

export async function executeRunner(
  runner: HarnessRunnerConfig,
  cwd: string = "."
): Promise<RunnerResult> {
  const startTime = Date.now();

  try {
    const { stdout, stderr } = await execAsync(runner.command, {
      cwd,
      timeout: runner.timeoutMs || 60000,
      env: { ...process.env, FORCE_COLOR: "0" },
    });

    const durationMs = Date.now() - startTime;

    return {
      runnerName: runner.name,
      type: runner.type,
      command: runner.command,
      passed: true,
      exitCode: 0,
      durationMs,
      stdout: stdout.toString(),
      stderr: stderr.toString(),
    };
  } catch (error: any) {
    const durationMs = Date.now() - startTime;
    const stdout = error.stdout ? error.stdout.toString() : "";
    const stderr = error.stderr ? error.stderr.toString() : "";
    const timedOut = error.killed && error.signal === "SIGTERM";

    const errorDetails = timedOut
      ? `⏱️ TIMEOUT: O runner '${runner.name}' excedeu o limite de ${runner.timeoutMs}ms.`
      : parseRunnerErrors(runner.type, stdout, stderr);

    return {
      runnerName: runner.name,
      type: runner.type,
      command: runner.command,
      passed: false,
      exitCode: typeof error.code === "number" ? error.code : 1,
      durationMs,
      stdout,
      stderr,
      errorDetails,
      timedOut,
    };
  }
}

export async function runAllHarness(
  runners: HarnessRunnerConfig[],
  cwd: string = "."
): Promise<HarnessExecutionSummary> {
  const startTime = Date.now();
  const results: RunnerResult[] = [];

  for (const runner of runners) {
    const result = await executeRunner(runner, cwd);
    results.push(result);
  }

  const totalDurationMs = Date.now() - startTime;
  const passedCount = results.filter((r) => r.passed).length;
  const failedCount = results.length - passedCount;

  return {
    allPassed: failedCount === 0,
    passedCount,
    failedCount,
    totalRunners: runners.length,
    totalDurationMs,
    results,
  };
}
