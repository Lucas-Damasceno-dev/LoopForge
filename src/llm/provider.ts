import type { LLMConfig } from "../config/schema.js";

export interface LLMResponse {
  content: string;
  modelUsed: string;
  isFallback: boolean;
  tokensUsed: number;
  estimatedCostUsd: number;
}

export class LLMEngine {
  private primaryModel: string;
  private fallbackModel: string;
  private provider: string;
  private baseUrl: string;
  private consecutiveFailures: number = 0;
  private isFallbackActive: boolean = false;

  constructor(config?: LLMConfig) {
    this.provider = config?.provider || "opencode";
    this.primaryModel = config?.model || "deepseek-v3";
    this.fallbackModel = config?.fallbackModel || "anthropic/claude-3-5-sonnet";
    this.baseUrl = config?.baseUrl || "http://localhost:8000";
  }

  public registerHarnessResult(passed: boolean): void {
    if (passed) {
      this.consecutiveFailures = 0;
      this.isFallbackActive = false;
    } else {
      this.consecutiveFailures++;
      if (this.consecutiveFailures >= 2) {
        this.isFallbackActive = true;
      }
    }
  }

  public getActiveModel(): { model: string; isFallback: boolean } {
    if (this.isFallbackActive) {
      return { model: this.fallbackModel, isFallback: true };
    }
    return { model: this.primaryModel, isFallback: false };
  }

  public async generateStep(prompt: string, maxRetries: number = 3): Promise<LLMResponse> {
    const { model, isFallback } = this.getActiveModel();

    let attempt = 0;
    while (attempt < maxRetries) {
      try {
        if (this.provider === "ollama") {
          return await this.callOllamaApi(prompt, model, isFallback);
        }

        if (this.provider === "vllm") {
          return await this.callVllmApi(prompt, model, isFallback);
        }

        // Simulação/OpenCode API mock provider
        await new Promise((resolve) => setTimeout(resolve, 50));
        const estimatedTokens = Math.ceil(prompt.length / 4) + 200;
        const costPerToken = isFallback ? 0.000015 : 0; // OpenCode free vs Claude
        const estimatedCostUsd = estimatedTokens * costPerToken;

        return {
          content: `[OpenCode Step Generated for Model ${model}]\n${prompt.slice(0, 100)}...`,
          modelUsed: model,
          isFallback,
          tokensUsed: estimatedTokens,
          estimatedCostUsd,
        };
      } catch (err) {
        attempt++;
        if (attempt >= maxRetries) throw err;
        const delay = Math.pow(2, attempt) * 100 + Math.random() * 50;
        await new Promise((res) => setTimeout(res, delay));
      }
    }

    throw new Error("Erro catastrófico ao comunicar com a API do modelo LLM.");
  }

  private async callOllamaApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    const response = await fetch(`${this.baseUrl}/api/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model.includes("deepseek") ? "qwen2.5-coder" : model,
        prompt,
        stream: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`Erro na API do Ollama: ${response.statusText}`);
    }

    const data: any = await response.json();
    return {
      content: data.response || "Resposta gerada pelo Ollama",
      modelUsed: `ollama/${model}`,
      isFallback,
      tokensUsed: data.eval_count || 150,
      estimatedCostUsd: 0,
    };
  }

  private async callVllmApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    const response = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
        max_tokens: 1024,
      }),
    });

    if (!response.ok) {
      throw new Error(`Erro na API do vLLM: ${response.statusText}`);
    }

    const data: any = await response.json();
    const content = data.choices?.[0]?.message?.content || "Resposta gerada pelo vLLM";
    const tokensUsed = data.usage?.total_tokens || 150;

    return {
      content,
      modelUsed: `vllm/${model}`,
      isFallback,
      tokensUsed,
      estimatedCostUsd: 0,
    };
  }
}
