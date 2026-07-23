import * as fs from "node:fs/promises";
import * as path from "node:path";
import { loadConfig } from "../config/loader.js";
import type { RunnerConfig } from "../config/schema.js";

export interface BootstrapResult {
  stackDetected: string;
  createdFiles: string[];
  runnersAdded: RunnerConfig[];
}

export async function bootstrapHarness(targetDir: string = "."): Promise<BootstrapResult> {
  const resolvedDir = path.resolve(targetDir);
  const createdFiles: string[] = [];
  const runnersAdded: RunnerConfig[] = [];
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
      { name: "Unit Tests (Vitest)", type: "unit", command: "npm test", timeoutMs: 60000, enabled: true },
      { name: "Linter / Check", type: "linter", command: "npm run check", timeoutMs: 30000, enabled: true }
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
      { name: "Pytest Suite", type: "unit", command: "pytest", timeoutMs: 60000, enabled: true }
    );
  } else if (hasCargoToml) {
    stackDetected = "Rust";
    runnersAdded.push(
      { name: "Cargo Test", type: "unit", command: "cargo test", timeoutMs: 60000, enabled: true },
      { name: "Cargo Clippy", type: "linter", command: "cargo clippy", timeoutMs: 30000, enabled: true }
    );
  } else {
    stackDetected = "Genérica / Script";
    runnersAdded.push(
      { name: "Linter Genérico", type: "custom", command: "echo 'Sensores ativos'", timeoutMs: 10000, enabled: true }
    );
  }

  try {
    const configPath = path.join(resolvedDir, ".loopforge.json");
    const config = await loadConfig(configPath);
    const existingNames = new Set(config.harness.runners.map((r) => r.name));
    for (const newRunner of runnersAdded) {
      if (!existingNames.has(newRunner.name)) {
        config.harness.runners.push(newRunner);
      }
    }
    await fs.writeFile(configPath, JSON.stringify(config, null, 2), "utf-8");
  } catch {}

  return {
    stackDetected,
    createdFiles,
    runnersAdded,
  };
}
