import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { MemoryManager } from "../src/memory/manager.js";

describe("LoopForge Memory Manager", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-memory-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve criar e anexar lições aprendidas no lessons.md", async () => {
    const memoryManager = new MemoryManager({ lessonsFile: "lessons.md", handoffFile: "handoff.md" }, tmpDir);
    await memoryManager.appendLesson("Falha de timeout", "Cuidado com timeouts longos no Playwright");

    const content = await memoryManager.readLessonsPrompt();
    expect(content).toContain("Cuidado com timeouts longos no Playwright");
  });

  it("deve atualizar o arquivo de handoff.md", async () => {
    const memoryManager = new MemoryManager({ lessonsFile: "lessons.md", handoffFile: "handoff.md" }, tmpDir);
    await memoryManager.updateHandoff("Fase 1 concluída", "Prosseguindo para a Fase 2", tmpDir);

    const content = await memoryManager.readHandoffPrompt();
    expect(content).toContain("Fase 1 concluída");
  });
});
