import * as fs from "node:fs/promises";
import * as path from "node:path";
import yaml from "js-yaml";
import { LoopForgeConfigSchema, type LoopForgeConfig } from "./schema.js";

export const DEFAULT_CONFIG_FILENAME = ".loopforge.json";

export async function loadConfig(configPath?: string, cwd: string = "."): Promise<LoopForgeConfig> {
  const possiblePaths = configPath
    ? [path.resolve(cwd, configPath)]
    : [
        path.resolve(cwd, ".loopforge.json"),
        path.resolve(cwd, ".loopforge.yml"),
        path.resolve(cwd, ".loopforge.yaml"),
      ];

  let resolvedPath = "";
  let rawData = "";

  for (const p of possiblePaths) {
    try {
      rawData = await fs.readFile(p, "utf-8");
      resolvedPath = p;
      break;
    } catch {
      // Ignore missing files when checking candidate config paths
    }
  }

  if (!resolvedPath || !rawData) {
    throw new Error(`Arquivo de configuração não encontrado em: ${possiblePaths[0]}. Execute 'loopforge init' para criar um.`);
  }

  try {
    let jsonParsed: unknown;
    if (resolvedPath.endsWith(".yml") || resolvedPath.endsWith(".yaml")) {
      jsonParsed = yaml.load(rawData);
    } else {
      jsonParsed = JSON.parse(rawData);
    }
    return LoopForgeConfigSchema.parse(jsonParsed);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`Validação de configuração falhou em '${path.basename(resolvedPath)}': ${message}`);
  }
}

export async function createDefaultConfig(targetDir: string = "."): Promise<string> {
  const filePath = path.resolve(targetDir, DEFAULT_CONFIG_FILENAME);
  const defaultConfig: LoopForgeConfig = LoopForgeConfigSchema.parse({
    projectName: "LoopForge Project",
    version: "5.0.0",
    harness: {
      runners: [
        { name: "Unit Tests", type: "unit", command: "npm test", enabled: true },
      ],
    },
  });

  await fs.writeFile(filePath, JSON.stringify(defaultConfig, null, 2), "utf-8");
  return filePath;
}
