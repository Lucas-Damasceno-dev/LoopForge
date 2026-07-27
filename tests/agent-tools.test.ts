import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { AgentTools, parseToolCallsFromText } from "../src/core/agent-tools.js";

describe("LoopForge Agent Tools", () => {
  let tempDir: string;
  let tools: AgentTools;

  beforeEach(async () => {
    tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-tools-test-"));
    tools = new AgentTools(tempDir);
  });

  afterEach(async () => {
    await fs.rm(tempDir, { recursive: true, force: true });
  });

  it("deve criar e gravar arquivo com write_file", async () => {
    const res = await tools.executeTool({
      name: "write_file",
      args: { path: "src/sample.ts", content: "console.log('hello');" },
    });

    expect(res.success).toBe(true);
    const content = await fs.readFile(path.join(tempDir, "src/sample.ts"), "utf-8");
    expect(content).toBe("console.log('hello');");
  });

  it("deve ler o conteúdo de um arquivo com read_file", async () => {
    await fs.writeFile(path.join(tempDir, "read.txt"), "conteudo de teste", "utf-8");

    const res = await tools.executeTool({
      name: "read_file",
      args: { path: "read.txt" },
    });

    expect(res.success).toBe(true);
    expect(res.output).toContain("conteudo de teste");
  });

  it("deve substituir trecho de código com replace_in_file", async () => {
    const filePath = path.join(tempDir, "code.ts");
    await fs.writeFile(filePath, "const a = 10;", "utf-8");

    const res = await tools.executeTool({
      name: "replace_in_file",
      args: { path: "code.ts", search: "const a = 10;", replace: "const a = 20;" },
    });

    expect(res.success).toBe(true);
    const content = await fs.readFile(filePath, "utf-8");
    expect(content).toBe("const a = 20;");
  });

  it("deve listar diretórios com list_directory", async () => {
    await fs.writeFile(path.join(tempDir, "file1.txt"), "a", "utf-8");
    await fs.mkdir(path.join(tempDir, "subfolder"), { recursive: true });

    const res = await tools.executeTool({
      name: "list_directory",
      args: { path: "." },
    });

    expect(res.success).toBe(true);
    expect(res.output).toContain("file1.txt");
    expect(res.output).toContain("subfolder/");
  });

  it("deve extrair chamadas de ferramenta de tags XML ou JSON em texto", () => {
    const textWithXml = `
Vou modificar o arquivo agora.
<tool_call>
{
  "name": "write_file",
  "args": { "path": "index.ts", "content": "export const x = 1;" }
}
</tool_call>
`;

    const calls = parseToolCallsFromText(textWithXml);
    expect(calls).toHaveLength(1);
    expect(calls[0].name).toBe("write_file");
    expect(calls[0].args.path).toBe("index.ts");
  });
});
