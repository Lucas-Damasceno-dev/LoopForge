import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as crypto from "node:crypto";

export interface CodeSymbol {
  name: string;
  kind: "function" | "class" | "interface" | "type" | "const";
  filePath: string;
  line: number;
  snippet: string;
}

export interface IndexCache {
  hashes: Record<string, string>;
  symbols: CodeSymbol[];
}

export class CodeIndexer {
  private indexPath: string;

  constructor(indexDir: string = ".loopforge/index") {
    this.indexPath = path.join(indexDir, "symbols.json");
  }

  private calculateHash(content: string): string {
    return crypto.createHash("sha256").update(content).digest("hex");
  }

  public async indexRepository(cwd: string = "."): Promise<number> {
    const resolvedDir = path.resolve(cwd);
    const indexDir = path.dirname(this.indexPath);
    await fs.mkdir(path.resolve(resolvedDir, indexDir), { recursive: true });

    let existingCache: IndexCache = { hashes: {}, symbols: [] };
    const fullIndexPath = path.resolve(resolvedDir, this.indexPath);

    try {
      const raw = await fs.readFile(fullIndexPath, "utf-8");
      existingCache = JSON.parse(raw);
    } catch {}

    const codeFiles = await this.findCodeFiles(resolvedDir);
    const symbols: CodeSymbol[] = [];
    const newHashes: Record<string, string> = {};

    for (const file of codeFiles) {
      const relativePath = path.relative(resolvedDir, file);
      try {
        const content = await fs.readFile(file, "utf-8");
        const hash = this.calculateHash(content);
        newHashes[relativePath] = hash;

        if (existingCache.hashes[relativePath] === hash) {
          const cachedFileSymbols = existingCache.symbols.filter(s => s.filePath === relativePath);
          symbols.push(...cachedFileSymbols);
          continue;
        }

        const extracted = this.extractSymbols(content, relativePath);
        symbols.push(...extracted);
      } catch {}
    }

    const updatedCache: IndexCache = {
      hashes: newHashes,
      symbols,
    };

    await fs.writeFile(fullIndexPath, JSON.stringify(updatedCache, null, 2), "utf-8");
    return symbols.length;
  }

  public async searchRelevantSnippets(query: string, topK: number = 3, cwd: string = "."): Promise<CodeSymbol[]> {
    const fullIndexPath = path.resolve(cwd, this.indexPath);
    try {
      const raw = await fs.readFile(fullIndexPath, "utf-8");
      const cache: IndexCache = JSON.parse(raw);
      const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);

      const scored = cache.symbols.map((sym) => {
        let score = 0;
        const targetText = `${sym.name} ${sym.snippet}`.toLowerCase();
        for (const term of queryTerms) {
          if (targetText.includes(term)) score += 1;
        }
        return { symbol: sym, score };
      });

      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, topK).map((s) => s.symbol);
    } catch {
      return [];
    }
  }

  private async findCodeFiles(dir: string): Promise<string[]> {
    const results: string[] = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.name === "node_modules" || entry.name === "dist") continue;
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        results.push(...(await this.findCodeFiles(fullPath)));
      } else if (/\.(ts|js|py|rs|go)$/.test(entry.name)) {
        results.push(fullPath);
      }
    }
    return results;
  }

  private extractSymbols(content: string, filePath: string): CodeSymbol[] {
    const lines = content.split("\n");
    const symbols: CodeSymbol[] = [];

    lines.forEach((line, idx) => {
      // Extended regex matching functions, classes, interfaces, types, consts, arrow functions, and class methods
      const match = line.match(/(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var)\s+([A-Za-z0-9_]+)/) ||
                    line.match(/(?:public|private|protected|async|static|\s)+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{/);
      if (match && match[1] && !["if", "for", "while", "switch", "catch"].includes(match[1])) {
        symbols.push({
          name: match[1],
          kind: line.includes("class") ? "class" : line.includes("interface") ? "interface" : line.includes("const") ? "const" : "function",
          filePath,
          line: idx + 1,
          snippet: line.trim(),
        });
      }
    });

    return symbols;
  }
}
