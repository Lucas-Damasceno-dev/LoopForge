import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { CodeIndexer } from "../src/indexer/rag.js";

describe("LoopForge Local RAG Code Indexer", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-rag-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve indexar símbolos do repositório e realizar busca semântica relevante com cache SHA-256", async () => {
    const srcDir = path.join(tmpDir, "src");
    await fs.mkdir(srcDir, { recursive: true });

    await fs.writeFile(
      path.join(srcDir, "user.ts"),
      `export class UserService {\n  public async authenticateUser() {\n    return true;\n  }\n}`
    );

    const indexer = new CodeIndexer();
    const totalChunks = await indexer.indexRepository(tmpDir);

    expect(totalChunks).toBeGreaterThan(0);

    const results = await indexer.searchRelevantSnippets("UserService", 1, tmpDir);
    expect(results.length).toBe(1);
    expect(results[0].snippet).toContain("UserService");
  });
});
