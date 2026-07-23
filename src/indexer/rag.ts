import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as crypto from "node:crypto";
import { LLMEngine } from "../llm/provider.js";

export interface CodeSymbol {
  name: string;
  kind: "function" | "class" | "interface" | "type" | "const";
  filePath: string;
  line: number;
  snippet: string;
  embedding?: number[];
}

export interface IndexCache {
  hashes: Record<string, string>;
  symbols: CodeSymbol[];
}

export function cosineSimilarity(vecA: number[], vecB: number[]): number {
  if (!vecA || !vecB || vecA.length !== vecB.length) return 0;
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < vecA.length; i++) {
    dotProduct += vecA[i] * vecB[i];
    normA += vecA[i] * vecA[i];
    normB += vecB[i] * vecB[i];
  }
  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

export class CodeIndexer {
  private indexPath: string;
  private llm: LLMEngine;

  constructor(indexDir: string = ".loopforge/index", llmEngine?: LLMEngine) {
    this.indexPath = path.join(indexDir, "symbols.json");
    this.llm = llmEngine || new LLMEngine();
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
        for (const sym of extracted) {
          try {
            const vec = await this.llm.generateEmbedding(`${sym.name} ${sym.snippet}`);
            sym.embedding = vec;
          } catch {}
        }
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
      const queryVec = await this.llm.generateEmbedding(query);
      const queryTerms = query.toLowerCase().split(/\s+/).filter(t => t.length > 2);

      const scored = cache.symbols.map((sym) => {
        let score = 0;
        if (sym.embedding && queryVec && sym.embedding.length === queryVec.length) {
          score = cosineSimilarity(queryVec, sym.embedding);
        }

        // Combine semantic similarity score with term-matching bonus
        const targetText = `${sym.name} ${sym.snippet}`.toLowerCase();
        for (const term of queryTerms) {
          if (targetText.includes(term)) score += 0.5;
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
