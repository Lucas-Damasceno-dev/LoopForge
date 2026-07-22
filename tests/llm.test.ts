import { describe, it, expect } from "vitest";
import { LLMEngine } from "../src/llm/provider.js";
import type { ProviderConfig } from "../src/config/schema.js";

describe("LoopForge LLM Engine & Model Fallback", () => {
  it("deve usar o modelo OpenCode DeepSeek v4 free por padrão quando consecutiveFailures é 0", () => {
    const config: ProviderConfig = {
      name: "opencode",
      model: "deepseek-v3",
      fallbackModel: "anthropic/claude-3-5-sonnet",
      enableModelFallback: true,
      fallbackFailureThreshold: 2,
    };

    const llm = new LLMEngine(config);
    const active = llm.getActiveModel(0);

    expect(active.model).toBe("deepseek-v3");
    expect(active.isFallback).toBe(false);
  });

  it("deve ativar o Model Fallback quando consecutiveFailures atinge o limite de 2 falhas", () => {
    const config: ProviderConfig = {
      name: "opencode",
      model: "deepseek-v3",
      fallbackModel: "anthropic/claude-3-5-sonnet",
      enableModelFallback: true,
      fallbackFailureThreshold: 2,
    };

    const llm = new LLMEngine(config);

    expect(llm.getActiveModel(1).isFallback).toBe(false);
    expect(llm.getActiveModel(2).isFallback).toBe(true);
    expect(llm.getActiveModel(2).model).toBe("anthropic/claude-3-5-sonnet");
  });
});
