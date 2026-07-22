import type { RunnerType } from "../config/schema.js";

export function parseRunnerErrors(
  type: RunnerType,
  stdout: string,
  stderr: string
): string {
  const combinedLog = `${stdout}\n${stderr}`.trim();
  if (!combinedLog) return "Nenhuma saída detalhada de erro capturada.";

  const lines = combinedLog.split("\n");

  switch (type) {
    case "typecheck": {
      // Filtrar erros comuns de TypeScript / Cargo / MyPy
      const tsErrors = lines.filter(
        (line) => line.includes("error TS") || line.includes("error[E") || line.includes("error:")
      );
      if (tsErrors.length > 0) {
        return tsErrors.slice(0, 15).join("\n");
      }
      break;
    }

    case "unit": {
      // Filtrar falhas do Vitest / Jest / Pytest
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
      // Filtrar falhas do Playwright / Cypress
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
      // Filtrar erros de linter (ESLint, Biome, Flake8)
      const linterErrors = lines.filter(
        (line) => line.includes("error") || line.includes("Warning") || line.includes("✖")
      );
      if (linterErrors.length > 0) {
        return linterErrors.slice(0, 15).join("\n");
      }
      break;
    }

    default:
      break;
  }

  // Fallback se não encontrar padrões específicos: retorna os últimos 2500 caracteres
  return combinedLog.length > 2500 ? combinedLog.slice(-2500) : combinedLog;
}
