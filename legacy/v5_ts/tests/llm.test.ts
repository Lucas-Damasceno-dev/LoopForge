import { describe, it, expect } from "vitest";
import { LLMEngine } from "../src/llm/provider.js";

describe("LoopForge LLM Engine & Model Fallback", () => {
  it("deve usar OpenCode DeepSeek v3 por padrão como modelo primário sem custo", () => {
    const llm = new LLMEngine();
    const active = llm.getActiveModel();
    expect(active.model).toBe("deepseek-v3");
    expect(active.isFallback).toBe(false);
  });

  it("deve ativar o Model Fallback quando falhas consecutivas do Harness atingem o limite de 2", () => {
    const llm = new LLMEngine({
      provider: "opencode",
      model: "deepseek-v3",
      fallbackModel: "anthropic/claude-3-5-sonnet",
    });

    llm.registerHarnessResult(false);
    expect(llm.getActiveModel().isFallback).toBe(false);

    llm.registerHarnessResult(false);
    expect(llm.getActiveModel().isFallback).toBe(true);
    expect(llm.getActiveModel().model).toBe("anthropic/claude-3-5-sonnet");
  });
});
