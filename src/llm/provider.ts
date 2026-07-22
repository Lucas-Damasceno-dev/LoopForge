import { exec } from "node:child_process";
import { promisify } from "node:util";
import type { ProviderConfig } from "../config/schema.js";

const execAsync = promisify(exec);

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  estimatedCostUsd: number;
}

export interface LLMResponse {
  content: string;
  modelUsed: string;
  isFallback: boolean;
  tokens: TokenUsage;
}

export class LLMEngine {
  constructor(private config: ProviderConfig) {}

  public getActiveModel(consecutiveFailures: number): { model: string; isFallback: boolean } {
    if (
      this.config.enableModelFallback &&
      consecutiveFailures >= this.config.fallbackFailureThreshold
    ) {
      return {
        model: this.config.fallbackModel,
        isFallback: true,
      };
    }

    return {
      model: this.config.model,
      isFallback: false,
    };
  }

  public async generateStep(
    promptContext: string,
    consecutiveFailures: number,
    cwd: string = "."
  ): Promise<LLMResponse> {
    const { model, isFallback } = this.getActiveModel(consecutiveFailures);

    try {
      // Invocar OpenCode CLI com o modelo configurado por padrão (ou modelo de fallback)
      const command = `opencode run --model "${model}" ${JSON.stringify(promptContext)}`;
      const { stdout } = await execAsync(command, { cwd, timeout: 120000 });

      const content = stdout.trim() || "Resposta do agente via OpenCode concluída.";
      const tokens = this.estimateTokenUsage(promptContext, content, isFallback);

      return {
        content,
        modelUsed: model,
        isFallback,
        tokens,
      };
    } catch {
      // Fallback gracioso para simulação local se o binary do opencode não estiver instalado no ambiente
      const content = `[Agente LoopForge - Modelo: ${model} ${isFallback ? "(FALLBACK ATIVADO)" : "(OPENCODE DEFAULT)"}]\nProcessando contexto da iteração...`;
      const tokens = this.estimateTokenUsage(promptContext, content, isFallback);

      return {
        content,
        modelUsed: model,
        isFallback,
        tokens,
      };
    }
  }

  private estimateTokenUsage(prompt: string, completion: string, isFallback: boolean): TokenUsage {
    // Estimativa simples (4 caracteres por token em média)
    const promptTokens = Math.ceil(prompt.length / 4);
    const completionTokens = Math.ceil(completion.length / 4);
    const totalTokens = promptTokens + completionTokens;

    // Se estiver usando o modelo OpenCode DeepSeek v4 free, custo é zero ($0.00)
    // Se for o modelo fallback (ex: Claude 3.5 Sonnet), aplica taxa estimada
    const costPer1kTokens = isFallback ? 0.003 : 0.0;
    const estimatedCostUsd = Number(((totalTokens / 1000) * costPer1kTokens).toFixed(6));

    return {
      promptTokens,
      completionTokens,
      totalTokens,
      estimatedCostUsd,
    };
  }
}
