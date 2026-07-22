import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { loadConfig, createDefaultConfig } from "../src/config/loader.js";
import { LoopForgeConfigSchema } from "../src/config/schema.js";

describe("LoopForge Config System", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-config-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("deve carregar configuração padrão se o objeto estiver vazio", () => {
    const config = LoopForgeConfigSchema.parse({});
    expect(config.strategy).toBe("creator");
    expect(config.guardrails.maxIterations).toBe(10);
    expect(config.guardrails.maxConsecutiveFailures).toBe(3);
    expect(config.harness.runners.length).toBeGreaterThan(0);
    expect(config.memory.lessonsFile).toBe(".loopforge/lessons.md");
    expect(config.memory.handoffFile).toBe(".loopforge/handoff.md");
  });

  it("deve criar e carregar um arquivo .loopforge.json com sucesso", async () => {
    const createdPath = await createDefaultConfig(tmpDir);
    expect(createdPath).toContain(".loopforge.json");

    const loadedConfig = await loadConfig(createdPath);
    expect(loadedConfig.name).toBe("LoopForge Project");
    expect(loadedConfig.guardrails.maxIterations).toBe(10);
  });

  it("deve lançar erro legível quando o arquivo de configuração não existe", async () => {
    const nonExistentPath = path.join(tmpDir, "does-not-exist.json");
    await expect(loadConfig(nonExistentPath)).rejects.toThrow("Arquivo de configuração não encontrado");
  });
});
