import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../config/loader.js";
import { LoopEngine } from "./loop-engine.js";

export interface WorkspaceConfig {
  projects: string[];
}

export class WorkspaceOrchestrator {
  private workspaceFile: string;

  constructor(workspaceFile: string = "loopforge-workspace.json") {
    this.workspaceFile = workspaceFile;
  }

  public async runWorkspaceLoops(cwd: string = "."): Promise<{ project: string; success: boolean; error?: string }[]> {
    const fullPath = path.resolve(cwd, this.workspaceFile);
    const raw = await fs.readFile(fullPath, "utf-8");
    const workspace: WorkspaceConfig = JSON.parse(raw);

    const results: { project: string; success: boolean; error?: string }[] = [];

    for (const projectRelativePath of workspace.projects) {
      const projectDir = path.resolve(cwd, projectRelativePath);
      try {
        const config = await loadConfig(path.join(projectDir, ".loopforge.json"));
        const engine = new LoopEngine(config, projectDir);
        const result = await engine.runLoop(async () => `Executou ciclo no workspace: ${projectRelativePath}`);
        results.push({ project: projectRelativePath, success: result.success });
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : String(err);
        console.warn(chalk.yellow(`⚠️ [Workspace] Falha ao executar loop no projeto '${projectRelativePath}': ${errorMsg}`));
        results.push({ project: projectRelativePath, success: false, error: errorMsg });
      }
    }

    return results;
  }
}
