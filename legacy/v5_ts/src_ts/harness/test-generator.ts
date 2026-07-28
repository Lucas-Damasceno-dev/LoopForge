import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { LLMEngine } from "../llm/provider.js";
import { detectProjectStack } from "./stack-detector.js";
import type { ProjectStack } from "./stack-detector.js";

export interface GeneratedTestFile {
  sourceFile: string;
  testFile: string;
  created: boolean;
  contentSnippet: string;
  hasLlmError?: boolean;
}

export class TestGenerator {
  private llm: LLMEngine;

  constructor(llmEngine?: LLMEngine) {
    this.llm = llmEngine || new LLMEngine();
  }

  public async generateTestsForUncoveredCode(cwd: string = ".", dryRun: boolean = false): Promise<GeneratedTestFile[]> {
    const resolvedDir = path.resolve(cwd);
    const stack = await detectProjectStack(resolvedDir);
    const sourceFiles = await this.findSourceFiles(resolvedDir, stack);
    const results: GeneratedTestFile[] = [];

    for (const srcFile of sourceFiles) {
      const relPath = path.relative(resolvedDir, srcFile);
      const ext = path.extname(srcFile);
      const baseName = path.basename(srcFile, ext);

      const testFilePath = this.resolveTestFilePath(resolvedDir, baseName, stack);
      const testExists = await fs.stat(testFilePath).then(() => true).catch(() => false);

      if (!testExists) {
        const sourceCode = await fs.readFile(srcFile, "utf-8");
        const prompt = this.buildPrompt(sourceCode, baseName, stack);
        let testContent = this.buildFallbackTemplate(baseName, stack);
        let hasLlmError = false;

        try {
          const llmRes = await this.llm.generateStep(prompt);
          if (llmRes.content && this.isValidLlmOutput(llmRes.content, stack)) {
            testContent = llmRes.content;
          }
        } catch (err) {
          hasLlmError = true;
          const errMsg = err instanceof Error ? err.message : String(err);
          console.warn(chalk.yellow(`⚠️ [TestGenerator] Falha ao consultar LLM Engine para '${relPath}': ${errMsg}. Usando template de teste seguro.`));
        }

        if (!dryRun) {
          await fs.mkdir(path.dirname(testFilePath), { recursive: true });
          await fs.writeFile(testFilePath, testContent, "utf-8");
        }

        results.push({
          sourceFile: relPath,
          testFile: path.relative(resolvedDir, testFilePath),
          created: !dryRun,
          contentSnippet: testContent.slice(0, 150) + "...",
          hasLlmError,
        });
      }
    }

    return results;
  }

  private resolveTestFilePath(dir: string, baseName: string, stack: ProjectStack): string {
    if (stack === "python") {
      return path.join(dir, "tests", `test_${baseName}.py`);
    }
    if (stack === "rust") {
      return path.join(dir, "tests", `${baseName}_test.rs`);
    }
    // node / generic
    return path.join(dir, "tests", `${baseName}.test.ts`);
  }

  private buildPrompt(sourceCode: string, baseName: string, stack: ProjectStack): string {
    const snippet = sourceCode.slice(0, 1000);
    switch (stack) {
      case "python":
        return `Generate pytest test functions for the following Python code:\n\n${snippet}`;
      case "rust":
        return `Generate Rust integration tests with cfg(test) for the following code:\n\n${snippet}`;
      default:
        // node / generic
        return `Gere uma suíte de testes unitários em TypeScript usando Vitest para o seguinte código:\n\n${snippet}`;
    }
  }

  private buildFallbackTemplate(baseName: string, stack: ProjectStack): string {
    switch (stack) {
      case "python":
        return `def test_baseline():\n    assert True\n`;
      case "rust":
        return `#[cfg(test)]\nmod tests {\n    use super::*;\n\n    #[test]\n    fn test_baseline() {\n        assert!(true);\n    }\n}\n`;
      default:
        // node / generic
        return `import { describe, it, expect } from "vitest";\n\ndescribe("${baseName} Test Suite", () => {\n  it("deve validar o funcionamento basico de ${baseName}", () => {\n    expect(true).toBe(true);\n  });\n});\n`;
    }
  }

  private isValidLlmOutput(content: string, stack: ProjectStack): boolean {
    switch (stack) {
      case "python":
        return /def test_/.test(content) || /import pytest/.test(content);
      case "rust":
        return /#\[test\]/.test(content) || /#\[cfg\(test\)\]/.test(content);
      default:
        // node / generic
        return content.includes("describe") || content.includes("it(");
    }
  }

  private async findSourceFiles(dir: string, stack?: ProjectStack): Promise<string[]> {
    const results: string[] = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });

    const extRegex =
      stack === "python"
        ? /\.py$/
        : stack === "rust"
        ? /\.rs$/
        : stack === "node"
        ? /\.(ts|js)$/
        : /\.(ts|js|py|rs)$/;

    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist" || entry.name === "tests") continue;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push(...(await this.findSourceFiles(fullPath, stack)));
      } else if (extRegex.test(entry.name) && !entry.name.includes("test")) {
        results.push(fullPath);
      }
    }
    return results;
  }
}
