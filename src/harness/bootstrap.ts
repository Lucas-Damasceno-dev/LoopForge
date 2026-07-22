import * as fs from "node:fs/promises";
import * as path from "node:path";
import { loadConfig } from "../config/loader.js";
import type { HarnessRunnerConfig } from "../config/schema.js";

export interface BootstrapResult {
  stackDetected: string;
  createdFiles: string[];
  runnersAdded: HarnessRunnerConfig[];
}

export async function bootstrapHarness(targetDir: string = "."): Promise<BootstrapResult> {
  const resolvedDir = path.resolve(targetDir);
  const createdFiles: string[] = [];
  const runnersAdded: HarnessRunnerConfig[] = [];
  let stackDetected = "Desconhecida";

  const hasPackageJson = await fs.stat(path.join(resolvedDir, "package.json")).then(() => true).catch(() => false);
  const hasPyproject = await fs.stat(path.join(resolvedDir, "pyproject.toml")).then(() => true).catch(() => false);
  const hasCargoToml = await fs.stat(path.join(resolvedDir, "Cargo.toml")).then(() => true).catch(() => false);

  if (hasPackageJson) {
    stackDetected = "Node.js / TypeScript";
    const sampleTestPath = path.join(resolvedDir, "tests/baseline.test.ts");
    await fs.mkdir(path.dirname(sampleTestPath), { recursive: true });
    
    const sampleTestContent = `import { describe, it, expect } from "vitest";

describe("Baseline Test Suite (Auto-Harness)", () => {
  it("deve passar como teste baseline do projeto", () => {
    expect(true).toBe(true);
  });
});
`;
    await fs.writeFile(sampleTestPath, sampleTestContent, { flag: "wx" }).catch(() => {});
    createdFiles.push(sampleTestPath);

    runnersAdded.push(
      { name: "Unit Tests (Vitest)", type: "unit", command: "npm test", timeoutMs: 60000 },
      { name: "Typecheck (TSC)", type: "typecheck", command: "npm run check", timeoutMs: 30000 }
    );
  } else if (hasPyproject) {
    stackDetected = "Python";
    const sampleTestPath = path.join(resolvedDir, "tests/test_baseline.py");
    await fs.mkdir(path.dirname(sampleTestPath), { recursive: true });

    const sampleTestContent = `def test_baseline():
    assert True
`;
    await fs.writeFile(sampleTestPath, sampleTestContent, { flag: "wx" }).catch(() => {});
    createdFiles.push(sampleTestPath);

    runnersAdded.push(
      { name: "Pytest Suite", type: "unit", command: "pytest", timeoutMs: 60000 }
    );
  } else if (hasCargoToml) {
    stackDetected = "Rust";
    runnersAdded.push(
      { name: "Cargo Test", type: "unit", command: "cargo test", timeoutMs: 60000 },
      { name: "Cargo Clippy", type: "linter", command: "cargo clippy", timeoutMs: 30000 }
    );
  } else {
    // Fallback genérico
    stackDetected = "Genérica / Script";
    runnersAdded.push(
      { name: "Linter Genérico", type: "custom", command: "echo 'Sensores ativos'", timeoutMs: 10000 }
    );
  }

  // Atualizar a configuração .loopforge.json se ela existir
  try {
    const configPath = path.join(resolvedDir, ".loopforge.json");
    const config = await loadConfig(configPath);
    config.harness.runners = runnersAdded;
    await fs.writeFile(configPath, JSON.stringify(config, null, 2), "utf-8");
  } catch {
    // Ignora se o arquivo .loopforge.json ainda não tiver sido inicializado
  }

  return {
    stackDetected,
    createdFiles,
    runnersAdded,
  };
}
