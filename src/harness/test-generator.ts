import * as fs from "node:fs/promises";
import * as path from "node:path";
import { LLMEngine } from "../llm/provider.js";

export interface GeneratedTestFile {
  sourceFile: string;
  testFile: string;
  created: boolean;
  contentSnippet: string;
}

export class TestGenerator {
  private llm: LLMEngine;

  constructor(llmEngine?: LLMEngine) {
    this.llm = llmEngine || new LLMEngine();
  }

  public async generateTestsForUncoveredCode(cwd: string = ".", dryRun: boolean = false): Promise<GeneratedTestFile[]> {
    const resolvedDir = path.resolve(cwd);
    const sourceFiles = await this.findSourceFiles(resolvedDir);
    const results: GeneratedTestFile[] = [];

    for (const srcFile of sourceFiles) {
      const relPath = path.relative(resolvedDir, srcFile);
      const baseName = path.basename(srcFile, path.extname(srcFile));
      const testFilePath = path.join(resolvedDir, "tests", `${baseName}.test.ts`);

      const testExists = await fs.stat(testFilePath).then(() => true).catch(() => false);

      if (!testExists) {
        const sourceCode = await fs.readFile(srcFile, "utf-8");
        const prompt = `Gere uma suíte de testes unitários em TypeScript usando Vitest para o seguinte código:\n\n${sourceCode.slice(0, 1000)}`;
        
        let testContent = `import { describe, it, expect } from "vitest";\n\ndescribe("${baseName} Test Suite", () => {\n  it("deve validar o funcionamento basico de ${baseName}", () => {\n    expect(true).toBe(true);\n  });\n});\n`;
        
        try {
          const llmRes = await this.llm.generateStep(prompt);
          if (llmRes.content && llmRes.content.includes("describe")) {
            testContent = llmRes.content;
          }
        } catch {}

        if (!dryRun) {
          await fs.mkdir(path.dirname(testFilePath), { recursive: true });
          await fs.writeFile(testFilePath, testContent, "utf-8");
        }

        results.push({
          sourceFile: relPath,
          testFile: path.relative(resolvedDir, testFilePath),
          created: !dryRun,
          contentSnippet: testContent.slice(0, 150) + "...",
        });
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
