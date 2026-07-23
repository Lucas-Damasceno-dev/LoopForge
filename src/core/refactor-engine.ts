import * as path from "node:path";
import { loadConfig } from "../config/loader.js";
import { LoopEngine } from "./loop-engine.js";
import { CodeIndexer } from "../indexer/rag.js";

export interface RefactorOptions {
  rule: string;
  cwd?: string;
}

export class RefactorEngine {
  private cwd: string;

  constructor(cwd: string = ".") {
    this.cwd = path.resolve(cwd);
  }

  public async runRefactor(options: RefactorOptions): Promise<{ success: boolean; filesAnalyzed: number; summary: string }> {
    const config = await loadConfig(path.join(this.cwd, ".loopforge.json"));
    const indexer = new CodeIndexer();
    const totalChunks = await indexer.indexRepository(this.cwd);
    const relevantSnippets = await indexer.searchRelevantSnippets(options.rule, 5, this.cwd);

    const engine = new LoopEngine(config, this.cwd);

    const snippetsText = relevantSnippets.map((s) => `[${s.filePath}:L${s.line}]\n${s.snippet}`).join("\n\n");
    const prompt = `TAREFA DE REFATORAÇÃO MASSIVA:
Regra de Refatoração: ${options.rule}
Total de Blocos de Código Indexados: ${totalChunks}

Trechos Relevantes Encontrados via RAG:
${snippetsText || "Nenhum trecho direto retornado pela busca."}

Instruções:
1. Examine os arquivos do repositório identificados no índice RAG.
2. Aplique a refatoração respeitando estritamente a regra informada sem quebrar testes pré-existentes.
3. Garanta 100% de compatibilidade com os sensores do Harness.`;

    const result = await engine.runLoop(async (fullContext, _iteration, llmEngine) => {
      const llmRes = await llmEngine.generateStep(`${prompt}\n\n${fullContext}`);
      return llmRes.content || `Refatoração processada para regra: ${options.rule}`;
    });

    return {
      success: result.success,
      filesAnalyzed: totalChunks,
      summary: `Refatoração encerrada com status: ${result.success ? "SUCESSO" : "FALHA"}. Motivo: ${result.stopReason}`,
    };
  }
}
