import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { readMemoryFile, appendLesson, updateHandoff, formatMemoryPrompt } from "../src/memory/manager.js";

describe("LoopForge Memory Manager", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-memory-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve criar e anexar lições aprendidas no lessons.md", async () => {
    const lessonsFile = path.join(tmpDir, "lessons.md");

    await appendLesson(lessonsFile, "Cuidado com timeouts longos no Playwright");
    const content = await readMemoryFile(lessonsFile, "Lições");

    expect(content).toContain("Cuidado com timeouts longos no Playwright");
  });

  it("deve atualizar o arquivo de handoff.md", async () => {
    const handoffFile = path.join(tmpDir, "handoff.md");

    await updateHandoff(handoffFile, "Fase 1 concluída, prosseguindo para a Fase 2.");
    const content = await readMemoryFile(handoffFile, "Handoff");

    expect(content).toContain("Fase 1 concluída, prosseguindo para a Fase 2.");
  });

  it("deve formatar o bloco de prompt de memória corretamente", () => {
    const lessons = "Lição 1: Testes E2E exigem porta aberta.";
    const handoff = "Próximo passo: Rodar linter.";

    const prompt = formatMemoryPrompt(lessons, handoff);

    expect(prompt).toContain("## 🧠 Memória Persistente do Repositório");
    expect(prompt).toContain("Lição 1: Testes E2E exigem porta aberta.");
    expect(prompt).toContain("Próximo passo: Rodar linter.");
  });
});
