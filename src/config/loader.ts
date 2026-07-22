import * as fs from "node:fs/promises";
import * as path from "node:path";
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
    } catch {}
  }

  if (!resolvedPath || !rawData) {
    throw new Error(`Arquivo de configuração não encontrado em: ${possiblePaths[0]}. Execute 'loopforge init' para criar um.`);
  }

  try {
    let json: any;
    if (resolvedPath.endsWith(".yml") || resolvedPath.endsWith(".yaml")) {
      // Basic YAML to JSON key-value parser for configuration
      json = parseSimpleYaml(rawData);
    } else {
      json = JSON.parse(rawData);
    }
    return LoopForgeConfigSchema.parse(json);
  } catch (error: any) {
    throw new Error(`Validação de configuração falhou em '${resolvedPath}': ${error.message}`);
  }
}

function parseSimpleYaml(yamlContent: string): any {
  const lines = yamlContent.split("\n");
  const result: any = {};
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const parts = trimmed.split(":");
    if (parts.length >= 2) {
      const key = parts[0].trim();
      const val = parts.slice(1).join(":").trim().replace(/^['"]|['"]$/g, "");
      if (val === "true") result[key] = true;
      else if (val === "false") result[key] = false;
      else if (!isNaN(Number(val))) result[key] = Number(val);
      else result[key] = val;
    }
  }
  return result;
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
