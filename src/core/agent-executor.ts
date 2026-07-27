import { AgentTools, parseToolCallsFromText, type ToolResult } from "./agent-tools.js";
import type { LLMEngine, LLMResponse } from "../llm/provider.js";
import { CodeIndexer } from "../indexer/rag.js";

export interface AgentStepExecutionResult {
  agentResponse: string;
  toolResults: ToolResult[];
  llmResponse: LLMResponse;
  filesModified: boolean;
}

export class AgentExecutor {
  private tools: AgentTools;
  private indexer: CodeIndexer;

  constructor(private cwd: string = ".") {
    this.tools = new AgentTools(cwd);
    this.indexer = new CodeIndexer();
  }

  public async buildEnhancedPrompt(promptContext: string, lastFailureLogs?: string): Promise<string> {
    let ragContext = "";
    try {
      if (lastFailureLogs) {
        const snippets = await this.indexer.searchRelevantSnippets(lastFailureLogs.slice(0, 300), 3, this.cwd);
        if (snippets.length > 0) {
          ragContext = "\n\n### 🔍 Trechos de Código Relevantes (RAG):\n" +
            snippets.map((s) => `[${s.filePath}:L${s.line}]\n${s.snippet}`).join("\n\n");
        }
      }
    } catch {
      /* ignore RAG lookup failure */
    }

    const toolInstructions = `
### 🧰 INSTRUÇÕES DE EXECUÇÃO DE FERRAMENTAS:
Você pode editar arquivos diretamente no repositório emitindo chamadas de ferramenta no formato XML:

<tool_call>
{
  "name": "write_file",
  "args": {
    "path": "caminho/do/arquivo.ts",
    "content": "conteúdo completo do arquivo"
  }
}
</tool_call>

Ou para substituir um trecho específico:
<tool_call>
{
  "name": "replace_in_file",
  "args": {
    "path": "caminho/do/arquivo.ts",
    "search": "código antigo",
    "replace": "código novo"
  }
}
</tool_call>

Se nenhum arquivo precisar de alteração, responda diretamente com sua análise.
`;

    return `${promptContext}${ragContext}\n${toolInstructions}`;
  }

  public async executeAgentStep(
    promptContext: string,
    llmEngine: LLMEngine,
    lastFailureLogs?: string
  ): Promise<AgentStepExecutionResult> {
    const fullPrompt = await this.buildEnhancedPrompt(promptContext, lastFailureLogs);
    const llmResponse = await llmEngine.generateStep(fullPrompt);

    const toolCalls = parseToolCallsFromText(llmResponse.content);
    const toolResults: ToolResult[] = [];
    let filesModified = false;

    for (const toolCall of toolCalls) {
      const res = await this.tools.executeTool(toolCall);
      toolResults.push(res);
      if (res.success && (res.toolName === "write_file" || res.toolName === "replace_in_file")) {
        filesModified = true;
      }
    }

    return {
      agentResponse: llmResponse.content,
      toolResults,
      llmResponse,
      filesModified,
    };
  }
}
