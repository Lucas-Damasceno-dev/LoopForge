import * as fs from "node:fs/promises";
import * as path from "node:path";
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

  public async runWorkspaceLoops(cwd: string = "."): Promise<{ project: string; success: boolean }[]> {
    const fullPath = path.resolve(cwd, this.workspaceFile);
    const raw = await fs.readFile(fullPath, "utf-8");
    const workspace: WorkspaceConfig = JSON.parse(raw);

    const results: { project: string; success: boolean }[] = [];

    for (const projectRelativePath of workspace.projects) {
      const projectDir = path.resolve(cwd, projectRelativePath);
      try {
        const config = await loadConfig(path.join(projectDir, ".loopforge.json"));
        const engine = new LoopEngine(config, projectDir);
        const result = await engine.runLoop(async () => `Executou ciclo no workspace: ${projectRelativePath}`);
        results.push({ project: projectRelativePath, success: result.success });
      } catch {
        results.push({ project: projectRelativePath, success: false });
      }
    }

    return results;
  }
}
