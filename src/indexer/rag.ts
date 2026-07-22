import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface CodeChunk {
  filePath: string;
  symbolName: string;
  snippet: string;
  score?: number;
}

export class CodeIndexer {
  private indexedChunks: CodeChunk[] = [];

  public async indexRepository(cwd: string = "."): Promise<number> {
    const resolvedDir = path.resolve(cwd);
    this.indexedChunks = [];

    await this.scanDirectory(resolvedDir, resolvedDir);

    const indexDir = path.join(resolvedDir, ".loopforge/index");
    await fs.mkdir(indexDir, { recursive: true });
    await fs.writeFile(
      path.join(indexDir, "symbols.json"),
      JSON.stringify(this.indexedChunks, null, 2),
      "utf-8"
    );

    return this.indexedChunks.length;
  }

  public searchRelevantSnippets(query: string, topK: number = 3): CodeChunk[] {
    const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length > 2);

    if (terms.length === 0 || this.indexedChunks.length === 0) {
      return this.indexedChunks.slice(0, topK);
    }

    const scored = this.indexedChunks.map((chunk) => {
      let score = 0;
      const lowerSnippet = chunk.snippet.toLowerCase();
      const lowerSymbol = chunk.symbolName.toLowerCase();

      for (const term of terms) {
        if (lowerSymbol.includes(term)) score += 5;
        if (lowerSnippet.includes(term)) score += 1;
      }

      return { ...chunk, score };
    });

    return scored
      .filter((c) => (c.score || 0) > 0)
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, topK);
  }

  private async scanDirectory(currentDir: string, rootDir: string): Promise<void> {
    const entries = await fs.readdir(currentDir, { withFileTypes: true }).catch(() => []);

    for (const entry of entries) {
      const fullPath = path.join(currentDir, entry.name);
      const relativePath = path.relative(rootDir, fullPath);

      if (entry.isDirectory()) {
        if (
          entry.name === "node_modules" ||
          entry.name === "dist" ||
          entry.name === ".git" ||
          entry.name === ".loopforge"
        ) {
          continue;
        }
        await this.scanDirectory(fullPath, rootDir);
      } else if (entry.isFile() && /\.(ts|js|py|rs|go)$/.test(entry.name)) {
        await this.indexFile(fullPath, relativePath);
      }
    }
  }

  private async indexFile(filePath: string, relativePath: string): Promise<void> {
    try {
      const content = await fs.readFile(filePath, "utf-8");
      const lines = content.split("\n");

      // Extrair assinaturas de função / classe / interface
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        if (
          line.includes("function") ||
          line.includes("class") ||
          line.includes("interface") ||
          line.includes("def ") ||
          line.includes("fn ")
        ) {
          const snippet = lines.slice(Math.max(0, i - 1), Math.min(lines.length, i + 10)).join("\n");
          this.indexedChunks.push({
            filePath: relativePath,
            symbolName: line.trim(),
            snippet,
          });
        }
      }
    } catch {
      // Ignorar erros de leitura de arquivo individual
    }
  }
}
