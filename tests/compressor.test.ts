import { describe, it, expect } from "vitest";
import { compressPromptContext } from "../src/llm/compressor.js";

describe("LoopForge Prompt Compressor", () => {
  it("deve manter contextos pequenos intactos", () => {
    const smallContext = "Contexto pequeno";
    const res = compressPromptContext(smallContext, 1000);
    expect(res.wasCompressed).toBe(false);
    expect(res.compressedContext).toBe(smallContext);
  });

  it("deve comprimir contextos longos preservando seções essenciais", () => {
    const longContext = "A".repeat(5000) + "\n\n" + "Lições Aprendidas: Teste ok\n\n" + "B".repeat(5000);
    const res = compressPromptContext(longContext, 2000);
    expect(res.wasCompressed).toBe(true);
    expect(res.compressedContext).toContain("Lições Aprendidas");
  });
});
