import * as fs from "node:fs/promises";
import * as path from "node:path";

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResult {
  toolName: string;
  success: boolean;
  output: string;
  error?: string;
}

export class AgentTools {
  constructor(private cwd: string = ".") {}

  public async executeTool(toolCall: ToolCall): Promise<ToolResult> {
    const name = toolCall.name.toLowerCase();
    const args = toolCall.args || {};

    try {
      switch (name) {
        case "read_file":
          return await this.readFile(String(args.path || ""));

        case "write_file":
          return await this.writeFile(String(args.path || ""), String(args.content || ""));

        case "replace_in_file":
        case "patch_file":
          return await this.replaceInFile(
            String(args.path || ""),
            String(args.search || args.target || ""),
            String(args.replace || args.replacement || "")
          );

        case "list_directory":
        case "list_files":
          return await this.listDirectory(String(args.path || "."));

        default:
          return {
            toolName: name,
            success: false,
            output: "",
            error: `Ferramenta '${name}' não é reconhecida. Ferramentas disponíveis: read_file, write_file, replace_in_file, list_directory`,
          };
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        toolName: name,
        success: false,
        output: "",
        error: `Erro ao executar ferramenta '${name}': ${msg}`,
      };
    }
  }

  private resolvePath(targetPath: string): string {
    return path.resolve(this.cwd, targetPath);
  }

  public async readFile(targetPath: string): Promise<ToolResult> {
    const fullPath = this.resolvePath(targetPath);
    const content = await fs.readFile(fullPath, "utf-8");
    return {
      toolName: "read_file",
      success: true,
      output: `[Conteúdo de ${targetPath}]:\n${content}`,
    };
  }

  public async writeFile(targetPath: string, content: string): Promise<ToolResult> {
    const fullPath = this.resolvePath(targetPath);
    await fs.mkdir(path.dirname(fullPath), { recursive: true });
    await fs.writeFile(fullPath, content || "", "utf-8");
    return {
      toolName: "write_file",
      success: true,
      output: `✔ Arquivo '${targetPath}' gravado com sucesso (${(content || "").length} bytes).`,
    };
  }

  public async replaceInFile(targetPath: string, search: string, replace: string): Promise<ToolResult> {
    const fullPath = this.resolvePath(targetPath);
    const fileContent = await fs.readFile(fullPath, "utf-8");
    if (!fileContent.includes(search)) {
      return {
        toolName: "replace_in_file",
        success: false,
        output: "",
        error: `Trecho de busca não foi encontrado no arquivo '${targetPath}'.`,
      };
    }
    const newContent = fileContent.replace(search, replace);
    await fs.writeFile(fullPath, newContent, "utf-8");
    return {
      toolName: "replace_in_file",
      success: true,
      output: `✔ Trecho substituído com sucesso em '${targetPath}'.`,
    };
  }

  public async listDirectory(dirPath: string = "."): Promise<ToolResult> {
    const fullPath = this.resolvePath(dirPath);
    const entries = await fs.readdir(fullPath, { withFileTypes: true });
    const formatted = entries
      .filter((e) => !e.name.startsWith(".") && e.name !== "node_modules" && e.name !== "dist")
      .map((e) => (e.isDirectory() ? `📁 ${e.name}/` : `📄 ${e.name}`))
      .join("\n");

    return {
      toolName: "list_directory",
      success: true,
      output: `[Conteúdo de ${dirPath}]:\n${formatted}`,
    };
  }
}

export function parseToolCallsFromText(text: string): ToolCall[] {
  if (!text || typeof text !== "string") return [];
  const toolCalls: ToolCall[] = [];

  // Match <tool_call> JSON </tool_call>
  const xmlRegex = /<tool_call>([\s\S]*?)<\/tool_call>/gi;
  let match: RegExpExecArray | null;

  while ((match = xmlRegex.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.name) {
        toolCalls.push({ name: parsed.name, args: parsed.args || parsed });
      }
    } catch {
      /* ignore invalid JSON tool call block */
    }
  }

  if (toolCalls.length > 0) return toolCalls;

  // Match JSON code blocks ```json { "name": ... } ```
  const codeBlockRegex = /```(?:json)?\s*(\{\s*"name"[\s\S]*?\})\s*```/gi;
  while ((match = codeBlockRegex.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1].trim());
      if (parsed.name) {
        toolCalls.push({ name: parsed.name, args: parsed.args || parsed });
      }
    } catch {
      /* ignore invalid JSON code block */
    }
  }

  return toolCalls;
}
