import * as fs from "node:fs/promises";
import * as path from "node:path";
import { LoopForgeConfigSchema, type LoopForgeConfig } from "./schema.js";

export const DEFAULT_CONFIG_FILENAME = ".loopforge.json";

export async function loadConfig(configPath?: string): Promise<LoopForgeConfig> {
  const resolvedPath = path.resolve(configPath || DEFAULT_CONFIG_FILENAME);

  try {
    const rawData = await fs.readFile(resolvedPath, "utf-8");
    const json = JSON.parse(rawData);
    return LoopForgeConfigSchema.parse(json);
  } catch (error: any) {
    if (error.code === "ENOENT") {
      throw new Error(`Arquivo de configuração não encontrado em: ${resolvedPath}. Execute 'loopforge init' para criar um.`);
    }
    if (error instanceof SyntaxError) {
      throw new Error(`Erro de sintaxe JSON em '${resolvedPath}': ${error.message}`);
    }
    throw new Error(`Validação de configuração falhou: ${error.message}`);
  }
}

export async function createDefaultConfig(targetDir: string = "."): Promise<string> {
  const filePath = path.resolve(targetDir, DEFAULT_CONFIG_FILENAME);
  const defaultConfig: LoopForgeConfig = LoopForgeConfigSchema.parse({
    projectName: "LoopForge Project",
    version: "3.0.0",
    harness: {
      runners: [
        { name: "Unit Tests", type: "unit", command: "npm test", enabled: true },
      ],
    },
  });

  await fs.writeFile(filePath, JSON.stringify(defaultConfig, null, 2), "utf-8");
  return filePath;
}
