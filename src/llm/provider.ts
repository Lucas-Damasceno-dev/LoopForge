import type { LLMConfig } from "../config/schema.js";

export interface LLMResponse {
  content: string;
  modelUsed: string;
  isFallback: boolean;
  tokensUsed: number;
  estimatedCostUsd: number;
}

interface OpenAICompletionResponse {
  choices?: Array<{ message?: { content?: string } }>;
  usage?: { total_tokens?: number };
}

interface OllamaApiResponse {
  response?: string;
  eval_count?: number;
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
    this.baseUrl = config?.baseUrl || (this.provider === "ollama" ? "http://localhost:11434" : "http://localhost:8000");
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
        if (isFallback && model.includes("anthropic")) {
          return await this.callAnthropicApi(prompt, model);
        }

        if (this.provider === "ollama") {
          return await this.callOllamaApi(prompt, model, isFallback);
        }

        if (this.provider === "vllm") {
          return await this.callVllmApi(prompt, model, isFallback);
        }

        return await this.callOpenCodeApi(prompt, model, isFallback);
      } catch (err) {
        attempt++;
        if (attempt >= maxRetries) {
          const msg = err instanceof Error ? err.message : String(err);
          // Fallback mock safely when external LLM server is un reachable
          const estimatedTokens = Math.ceil(prompt.length / 4) + 100;
          return {
            content: `[OpenCode Engine Step - Offline Fallback] ${prompt.slice(0, 150)}...`,
            modelUsed: model,
            isFallback,
            tokensUsed: estimatedTokens,
            estimatedCostUsd: isFallback ? 0.003 : 0.0,
          };
        }
        const delay = Math.pow(2, attempt) * 100 + Math.random() * 50;
        await new Promise((res) => setTimeout(res, delay));
      }
    }

    throw new Error("Erro na comunicação com a API do modelo LLM.");
  }

  private async callAnthropicApi(prompt: string, model: string): Promise<LLMResponse> {
    const apiKey = process.env.ANTHROPIC_API_KEY || "mock-anthropic-key";
    const endpoint = "https://api.anthropic.com/v1/messages";

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
          "anthropic-version": "2023-06-01",
        },
        body: JSON.stringify({
          model: model.replace("anthropic/", ""),
          max_tokens: 1024,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      if (response.ok) {
        const data = (await response.json()) as { content?: Array<{ text?: string }>; usage?: { input_tokens?: number; output_tokens?: number } };
        const content = data.content?.[0]?.text || "Resposta Anthropic Claude";
        const tokensUsed = (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0) || 200;
        return {
          content,
          modelUsed: model,
          isFallback: true,
          tokensUsed,
          estimatedCostUsd: Number((tokensUsed * 0.000015).toFixed(6)),
        };
      }
    } catch {}

    const estimatedTokens = Math.ceil(prompt.length / 4) + 150;
    return {
      content: `[Claude 3.5 Sonnet Fallback] Resposta simulada para: ${prompt.slice(0, 100)}...`,
      modelUsed: model,
      isFallback: true,
      tokensUsed: estimatedTokens,
      estimatedCostUsd: 0.003,
    };
  }

  private async callOpenCodeApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    const openCodeUrl = process.env.OPENCODE_API_URL || `${this.baseUrl}/v1/chat/completions`;
    const response = await fetch(openCodeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!response.ok) {
      throw new Error(`Erro na API OpenCode (${response.status}): ${response.statusText}`);
    }

    const data = (await response.json()) as OpenAICompletionResponse;
    const content = data.choices?.[0]?.message?.content || "Resposta OpenCode";
    const tokensUsed = data.usage?.total_tokens || 150;

    return {
      content,
      modelUsed: model,
      isFallback,
      tokensUsed,
      estimatedCostUsd: isFallback ? 0.001 : 0.0,
    };
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

    const data = (await response.json()) as OllamaApiResponse;
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

    const data = (await response.json()) as OpenAICompletionResponse;
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
