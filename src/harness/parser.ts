import type { RunnerType } from "../config/schema.js";

export function extractErrorDetails(combinedLog: string, type: RunnerType): string {
  if (!combinedLog.trim()) return "Nenhuma saída detalhada de erro capturada.";

  const lines = combinedLog.split("\n");

  switch (type) {
    case "unit": {
      const failureLines = lines.filter(
        (line) =>
          line.includes("FAIL") ||
          line.includes("AssertionError") ||
          line.includes("Expected:") ||
          line.includes("Received:") ||
          line.includes("✕ ") ||
          line.includes("FAILED ")
      );
      if (failureLines.length > 0) {
        return failureLines.slice(0, 20).join("\n");
      }
      break;
    }

    case "e2e": {
      const e2eFailures = lines.filter(
        (line) =>
          line.includes("Error:") ||
          line.includes("waiting for locator") ||
          line.includes("TimeoutError") ||
          line.includes("element not found") ||
          line.includes("toBeVisible") ||
          line.includes("page.click")
      );
      if (e2eFailures.length > 0) {
        return e2eFailures.slice(0, 25).join("\n");
      }
      break;
    }

    case "linter": {
      const linterErrors = lines.filter(
        (line) => line.includes("error") || line.includes("Warning") || line.includes("✖") || line.includes("error TS")
      );
      if (linterErrors.length > 0) {
        return linterErrors.slice(0, 15).join("\n");
      }
      break;
    }

    default:
      break;
  }

  return combinedLog.length > 2500 ? combinedLog.slice(-2500) : combinedLog;
}

export function parseRunnerErrors(type: RunnerType, stdout: string, stderr: string): string {
  return extractErrorDetails(`${stdout}\n${stderr}`, type);
}
