import { exec, type ExecException } from "node:child_process";
import { promisify } from "node:util";
import type { HarnessConfig } from "../config/schema.js";
import type { RunnerResult, HarnessExecutionSummary } from "./types.js";
import { extractErrorDetails } from "./parser.js";

const execAsync = promisify(exec);

interface ExecError extends ExecException {
  stdout?: string;
  stderr?: string;
  code?: number;
  killed?: boolean;
}

export async function runSingleRunner(
  runnerName: string,
  runnerType: "unit" | "linter" | "e2e" | "custom",
  command: string,
  cwd: string = ".",
  timeoutMs: number = 60000
): Promise<RunnerResult> {
  const startTime = Date.now();
  try {
    const { stdout, stderr } = await execAsync(command, {
      cwd,
      timeout: timeoutMs,
    });
    const durationMs = Date.now() - startTime;
    return {
      runnerName,
      type: runnerType,
      command,
      passed: true,
      exitCode: 0,
      durationMs,
      stdout,
      stderr,
    };
  } catch (error: unknown) {
    const execErr = error as ExecError;
    const durationMs = Date.now() - startTime;
    const stdout = execErr?.stdout || "";
    const stderr = execErr?.stderr || "";
    const combinedOutput = `${stdout}\n${stderr}`;
    const errorDetails = extractErrorDetails(combinedOutput, runnerType);

    return {
      runnerName,
      type: runnerType,
      command,
      passed: false,
      exitCode: execErr?.code || 1,
      durationMs,
      stdout,
      stderr,
      errorDetails,
      timedOut: execErr?.killed || false,
    };
  }
}

export async function runHarness(
  config: HarnessConfig,
  cwd: string = "."
): Promise<HarnessExecutionSummary> {
  const startTime = Date.now();
  const enabledRunners = config.runners.filter((r) => r.enabled !== false);
  const isParallel = config.parallel !== false && !config.stopOnFirstFailure;

  let results: RunnerResult[] = [];

  if (isParallel) {
    results = await Promise.all(
      enabledRunners.map((runner) =>
        runSingleRunner(runner.name, runner.type, runner.command, cwd, runner.timeoutMs)
      )
    );
  } else {
    for (const runner of enabledRunners) {
      const result = await runSingleRunner(
        runner.name,
        runner.type,
        runner.command,
        cwd,
        runner.timeoutMs
      );
      results.push(result);
      if (config.stopOnFirstFailure && !result.passed) {
        break;
      }
    }
  }

  const totalDurationMs = Date.now() - startTime;
  const passedCount = results.filter((r) => r.passed).length;
  const failedCount = results.length - passedCount;
  const allPassed = failedCount === 0;

  return {
    allPassed,
    passedCount,
    failedCount,
    totalRunners: results.length,
    totalDurationMs,
    results,
  };
}
