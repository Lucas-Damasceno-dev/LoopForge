import { spawn, execSync, type ChildProcess } from "node:child_process";
import * as fs from "node:fs";
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
  private serverProcess: ChildProcess | null = null;
  private serverStarting: boolean = false;

  constructor(config?: LLMConfig) {
    this.provider = config?.provider || "opencode";
    this.primaryModel = config?.model || "deepseek-v3";
    this.fallbackModel = config?.fallbackModel || "anthropic/claude-3-5-sonnet";
    this.baseUrl = config?.baseUrl || (this.provider === "ollama" ? "http://localhost:11434" : "http://localhost:8000");
  }

  private findOpenCode(): string | null {
    const candidates: string[] = [];
    try {
      const which = execSync("which opencode 2>/dev/null", { encoding: "utf-8" }).trim();
      if (which) candidates.push(which);
    } catch {}
<<<<<<< Updated upstream
    const home = process.env.HOME || "";
    const sudoUser = process.env.SUDO_USER || "";
    const sudoHome = sudoUser ? `/home/${sudoUser}` : "";
    for (const prefix of [home, sudoHome, "/usr", "/usr/local"]) {
=======

    const home = process.env.HOME || "";
    const sudoUser = process.env.SUDO_USER || "";
    const sudoHome = sudoUser ? `/home/${sudoUser}` : "";
    const prefixes = [home, sudoHome, "/usr", "/usr/local"];
    for (const prefix of prefixes) {
>>>>>>> Stashed changes
      if (!prefix) continue;
      for (const subdir of ["/bin/opencode", "/lib/node_modules/@opencode-ai/opencode/dist/cli/index.js"]) {
        const full = prefix + subdir;
        if (fs.existsSync(full)) candidates.push(full);
      }
    }
<<<<<<< Updated upstream
    for (const candidate of candidates) {
      try { fs.accessSync(candidate, fs.constants.X_OK); return candidate; } catch {
=======

    for (const candidate of candidates) {
      try {
        fs.accessSync(candidate, fs.constants.X_OK);
        return candidate;
      } catch {
>>>>>>> Stashed changes
        if (candidate.endsWith(".js")) return `node ${candidate}`;
      }
    }
    return null;
  }

  private async ensureServer(): Promise<boolean> {
    if (this.provider !== "opencode") return false;
    if (await this.isServerRunning()) return true;
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
    if (this.serverStarting) {
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 500));
        if (await this.isServerRunning()) return true;
      }
      return false;
    }
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
    this.serverStarting = true;
    try {
      const opencodePath = this.findOpenCode();
      if (!opencodePath) {
        console.warn("[LLM] opencode não encontrado. Instale com: npm i -g @opencode-ai/opencode");
        return false;
      }
<<<<<<< Updated upstream
      const port = new URL(this.baseUrl).port || "8000";
      console.warn(`[LLM] Iniciando servidor OpenCode em --port ${port}...`);
      const [cmd, ...args] = opencodePath.split(" ");
      this.serverProcess = spawn(cmd, [...args, "serve", "--port", port, "--print-logs"], {
        stdio: ["ignore", "pipe", "pipe"], detached: false,
      });
=======

      const port = new URL(this.baseUrl).port || "8000";
      console.warn(`[LLM] Iniciando servidor OpenCode em --port ${port}...`);

      const [cmd, ...args] = opencodePath.split(" ");
      this.serverProcess = spawn(cmd, [...args, "serve", "--port", port, "--print-logs"], {
        stdio: ["ignore", "pipe", "pipe"],
        detached: false,
      });

>>>>>>> Stashed changes
      this.serverProcess.stdout?.on("data", (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) process.stderr.write(`[opencode-serve] ${msg}\n`);
      });
      this.serverProcess.stderr?.on("data", (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) process.stderr.write(`[opencode-serve] ${msg}\n`);
      });
      this.serverProcess.on("exit", (code) => {
        console.warn(`[LLM] Servidor OpenCode encerrado (código: ${code})`);
        this.serverProcess = null;
      });
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 500));
        if (await this.isServerRunning()) {
          console.warn(`[LLM] Servidor OpenCode pronto em ${this.baseUrl}`);
          return true;
        }
      }
<<<<<<< Updated upstream
=======

>>>>>>> Stashed changes
      console.warn("[LLM] Servidor OpenCode não respondeu após 30s");
      this.killServer();
      return false;
    } catch (err) {
      console.warn(`[LLM] Falha ao iniciar servidor OpenCode: ${err instanceof Error ? err.message : String(err)}`);
      return false;
    } finally {
      this.serverStarting = false;
    }
  }

  private async isServerRunning(): Promise<boolean> {
    try {
      const res = await fetch(`${this.baseUrl}/v1/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model: this.primaryModel, messages: [{ role: "user", content: "ping" }], max_tokens: 1 }),
        signal: AbortSignal.timeout(2000),
      });
      return res.ok;
    } catch { return false; }
  }

  private killServer(): void {
    if (this.serverProcess) {
      try { this.serverProcess.kill("SIGTERM"); } catch {}
      this.serverProcess = null;
    }
  }

  public async generateEmbedding(text: string): Promise<number[]> {
    try {
      const endpoint = process.env.OPENCODE_EMBEDDINGS_URL || `${this.baseUrl}/v1/embeddings`;
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input: text, model: "text-embedding-3-small" }),
      });
      if (response.ok) {
        const data = (await response.json()) as { data?: Array<{ embedding?: number[] }> };
        if (data.data?.[0]?.embedding) return data.data[0].embedding;
      }
    } catch {}

    const dim = 64;
    const vec = new Array(dim).fill(0);
    const words = text.toLowerCase().split(/\W+/).filter(Boolean);
    for (let i = 0; i < words.length; i++) {
      let hash = 0;
      for (let j = 0; j < words[i].length; j++) { hash = (hash << 5) - hash + words[i].charCodeAt(j); hash |= 0; }
      vec[Math.abs(hash) % dim] += 1;
    }
    const norm = Math.sqrt(vec.reduce((s, v) => s + v * v, 0));
    return norm === 0 ? vec : vec.map((v) => v / norm);
  }

  public registerHarnessResult(passed: boolean): void {
    if (passed) { this.consecutiveFailures = 0; this.isFallbackActive = false; }
    else { this.consecutiveFailures++; if (this.consecutiveFailures >= 2) this.isFallbackActive = true; }
  }

  public getActiveModel(): { model: string; isFallback: boolean } {
    return this.isFallbackActive
      ? { model: this.fallbackModel, isFallback: true }
      : { model: this.primaryModel, isFallback: false };
  }

  public async generateStep(prompt: string, maxRetries: number = 3): Promise<LLMResponse> {
    const { model, isFallback } = this.getActiveModel();
    let attempt = 0;
    while (attempt < maxRetries) {
      try {
<<<<<<< Updated upstream
        if (isFallback && model.includes("anthropic")) {
          return await this.callAnthropicApi(prompt, model);
        }
        if (this.provider === "ollama") {
          return await this.callOllamaApi(prompt, model, isFallback);
        }
        if (this.provider === "vllm") {
          return await this.callVllmApi(prompt, model, isFallback);
        }
=======
        if (isFallback && model.includes("anthropic")) return await this.callAnthropicApi(prompt, model);
        if (this.provider === "ollama") return await this.callOllamaApi(prompt, model, isFallback);
        if (this.provider === "vllm") return await this.callVllmApi(prompt, model, isFallback);
>>>>>>> Stashed changes
        return await this.callOpenCodeApi(prompt, model, isFallback);
      } catch (err) {
        attempt++;
        if (attempt >= maxRetries) {
          const msg = err instanceof Error ? err.message : String(err);
<<<<<<< Updated upstream
          const estimatedTokens = Math.ceil(prompt.length / 4) + 100;
          return {
            content: `[FALLBACK] ${msg}`,
            modelUsed: model,
            isFallback: true,
            tokensUsed: estimatedTokens,
            estimatedCostUsd: 0.0,
          };
=======
          return { content: `[FALLBACK] ${msg}`, modelUsed: model, isFallback: true, tokensUsed: 0, estimatedCostUsd: 0 };
>>>>>>> Stashed changes
        }
        await new Promise((r) => setTimeout(r, Math.pow(2, attempt) * 100 + Math.random() * 50));
      }
    }
    throw new Error("Erro na comunicação com a API do modelo LLM.");
  }

  private async callOpenCodeApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    if (!(await this.isServerRunning())) {
      const started = await this.ensureServer();
<<<<<<< Updated upstream
      if (!started) {
        throw new Error(
          `Servidor OpenCode indisponível em ${this.baseUrl}. ` +
          `Instale com 'npm i -g @opencode-ai/opencode' ou inicie manualmente com 'opencode serve --port ${new URL(this.baseUrl).port || "8000"}'`
        );
      }
      // Aguarda um momento para o modelo carregar
      await new Promise((r) => setTimeout(r, 1000));
    }

    // Tenta o modelo primário, depois fallbacks
    const modelsToTry = [model, "deepseek-v4-flash", "deepseek-chat", "gpt-4o-mini"];
    let lastError: string = "";

    for (const tryModel of modelsToTry) {
      try {
        const openCodeUrl = process.env.OPENCODE_API_URL || `${this.baseUrl}/v1/chat/completions`;
        const response = await fetch(openCodeUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            model: tryModel,
            messages: [{ role: "user", content: prompt }],
          }),
          signal: AbortSignal.timeout(30000),
        });

        if (response.ok) {
          const data = (await response.json()) as OpenAICompletionResponse;
          const content = data.choices?.[0]?.message?.content || "Resposta OpenCode";
          return {
            content,
            modelUsed: tryModel,
            isFallback,
            tokensUsed: data.usage?.total_tokens || 150,
            estimatedCostUsd: isFallback ? 0.001 : 0.0,
          };
        }

        lastError = `Erro na API OpenCode (${response.status}): ${response.statusText}`;
        if (response.status !== 404 && response.status !== 400) {
          throw new Error(lastError);
        }
        // 404/400 = modelo não encontrado, tenta próximo
      } catch (err) {
        if (err instanceof Error && err.name === "TimeoutError") {
          throw new Error("Timeout na requisição ao servidor OpenCode (30s)");
        }
        lastError = err instanceof Error ? err.message : String(err);
        // Se não for erro de modelo, propaga
        if (!lastError.includes("model") && !lastError.includes("404") && !lastError.includes("400")) {
          throw err;
        }
      }
    }

    throw new Error(lastError || "Nenhum modelo disponível no servidor OpenCode");
=======
      if (!started) throw new Error(
        `Servidor OpenCode indisponível em ${this.baseUrl}. ` +
        `Instale com 'npm i -g @opencode-ai/opencode' ou inicie manualmente com 'opencode serve --port ${new URL(this.baseUrl).port || "8000"}'`
      );
    }

    const openCodeUrl = process.env.OPENCODE_API_URL || `${this.baseUrl}/v1/chat/completions`;
    const response = await fetch(openCodeUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }] }),
    });
    if (!response.ok) throw new Error(`Erro na API OpenCode (${response.status}): ${response.statusText}`);

    const data = (await response.json()) as OpenAICompletionResponse;
    return {
      content: data.choices?.[0]?.message?.content || "Resposta OpenCode",
      modelUsed: model, isFallback,
      tokensUsed: data.usage?.total_tokens || 150,
      estimatedCostUsd: isFallback ? 0.001 : 0.0,
    };
>>>>>>> Stashed changes
  }

  private async callAnthropicApi(prompt: string, model: string): Promise<LLMResponse> {
    const apiKey = process.env.ANTHROPIC_API_KEY || "mock-anthropic-key";
    try {
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
        body: JSON.stringify({ model: model.replace("anthropic/", ""), max_tokens: 1024, messages: [{ role: "user", content: prompt }] }),
      });
      if (response.ok) {
        const data = (await response.json()) as { content?: Array<{ text?: string }>; usage?: { input_tokens?: number; output_tokens?: number } };
        const tokensUsed = (data.usage?.input_tokens || 0) + (data.usage?.output_tokens || 0) || 200;
        return { content: data.content?.[0]?.text || "Resposta Anthropic Claude", modelUsed: model, isFallback: true, tokensUsed, estimatedCostUsd: Number((tokensUsed * 0.000015).toFixed(6)) };
      }
    } catch {}
    return { content: `[Claude Fallback] Resposta simulada`, modelUsed: model, isFallback: true, tokensUsed: 100, estimatedCostUsd: 0.003 };
  }

  private async callOllamaApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    const response = await fetch(`${this.baseUrl}/api/generate`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model: model.includes("deepseek") ? "qwen2.5-coder" : model, prompt, stream: false }),
    });
    if (!response.ok) throw new Error(`Erro na API do Ollama: ${response.statusText}`);
    const data = (await response.json()) as OllamaApiResponse;
    return { content: data.response || "Resposta gerada pelo Ollama", modelUsed: `ollama/${model}`, isFallback, tokensUsed: data.eval_count || 150, estimatedCostUsd: 0 };
  }

  private async callVllmApi(prompt: string, model: string, isFallback: boolean): Promise<LLMResponse> {
    const response = await fetch(`${this.baseUrl}/v1/chat/completions`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model, messages: [{ role: "user", content: prompt }], max_tokens: 1024 }),
    });
    if (!response.ok) throw new Error(`Erro na API do vLLM: ${response.statusText}`);
    const data = (await response.json()) as OpenAICompletionResponse;
    return { content: data.choices?.[0]?.message?.content || "Resposta gerada pelo vLLM", modelUsed: `vllm/${model}`, isFallback, tokensUsed: data.usage?.total_tokens || 150, estimatedCostUsd: 0 };
  }
}