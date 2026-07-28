import * as fs from "node:fs/promises";
import * as path from "node:path";

export type ProjectStack = "node" | "python" | "rust" | "generic";

/**
 * Detect the project stack by checking for well-known config files.
 * Order of precedence: package.json -> pyproject.toml -> Cargo.toml -> generic
 */
export async function detectProjectStack(cwd: string): Promise<ProjectStack> {
  const resolvedDir = path.resolve(cwd);

  const hasPackageJson = await fs.stat(path.join(resolvedDir, "package.json")).then(() => true).catch(() => false);
  if (hasPackageJson) return "node";

  const hasPyproject = await fs.stat(path.join(resolvedDir, "pyproject.toml")).then(() => true).catch(() => false);
  if (hasPyproject) return "python";

  const hasCargoToml = await fs.stat(path.join(resolvedDir, "Cargo.toml")).then(() => true).catch(() => false);
  if (hasCargoToml) return "rust";

  return "generic";
}
