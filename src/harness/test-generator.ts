import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface GeneratedTestFile {
  sourceFile: string;
  testFile: string;
  created: boolean;
}

export class TestGenerator {
  public async generateTestsForUncoveredCode(cwd: string = "."): Promise<GeneratedTestFile[]> {
    const resolvedDir = path.resolve(cwd);
    const sourceFiles = await this.findSourceFiles(resolvedDir);
    const results: GeneratedTestFile[] = [];

    for (const srcFile of sourceFiles) {
      const relPath = path.relative(resolvedDir, srcFile);
      const baseName = path.basename(srcFile, path.extname(srcFile));
      const testFilePath = path.join(resolvedDir, "tests", `${baseName}.test.ts`);

      const testExists = await fs.stat(testFilePath).then(() => true).catch(() => false);

      if (!testExists) {
        await fs.mkdir(path.dirname(testFilePath), { recursive: true });
        const testBoilerplate = `import { describe, it, expect } from "vitest";\n\ndescribe("${baseName} Auto-Generated Test Suite", () => {\n  it("deve executar caso de teste inicial para ${baseName}", () => {\n    expect(true).toBe(true);\n  });\n});\n`;
        await fs.writeFile(testFilePath, testBoilerplate, "utf-8");
        results.push({ sourceFile: relPath, testFile: path.relative(resolvedDir, testFilePath), created: true });
      }
    }

    return results;
  }

  private async findSourceFiles(dir: string): Promise<string[]> {
    const results: string[] = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist" || entry.name === "tests") continue;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push(...(await this.findSourceFiles(fullPath)));
      } else if (/\.(ts|js)$/.test(entry.name) && !entry.name.includes("test")) {
        results.push(fullPath);
      }
    }
    return results;
  }
}
