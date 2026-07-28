import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { loadConfig } from "../config/loader.js";
import { LoopEngine } from "./loop-engine.js";

export interface WorkspaceConfig {
  projects: string[];
}

export interface WorkspaceRunResult {
  project: string;
  success: boolean;
  error?: string;
}

export class WorkspaceOrchestrator {
  private workspaceFile: string;

  constructor(workspaceFile: string = "loopforge-workspace.json") {
    this.workspaceFile = workspaceFile;
  }

  public async runWorkspaceLoops(
    cwd: string = ".",
    options: { parallel?: boolean; concurrency?: number } = {}
  ): Promise<WorkspaceRunResult[]> {
    const fullPath = path.resolve(cwd, this.workspaceFile);
    const raw = await fs.readFile(fullPath, "utf-8");
    const workspace: WorkspaceConfig = JSON.parse(raw);

    const concurrencyLimit = options.concurrency || 3;
    const isParallel = options.parallel ?? false;

    if (!isParallel) {
      const results: WorkspaceRunResult[] = [];
      for (const projectRelativePath of workspace.projects) {
        const res = await this.runSingleProject(cwd, projectRelativePath);
        results.push(res);
      }
      return results;
    }

    // Parallel execution with semaphore limit
    const queue = [...workspace.projects];
    const results: WorkspaceRunResult[] = [];
    const activeWorkers: Promise<void>[] = [];

    const worker = async () => {
      while (queue.length > 0) {
        const projectRelativePath = queue.shift();
        if (!projectRelativePath) break;
        const res = await this.runSingleProject(cwd, projectRelativePath);
        results.push(res);
      }
    };

    for (let i = 0; i < Math.min(concurrencyLimit, workspace.projects.length); i++) {
      activeWorkers.push(worker());
    }

    await Promise.all(activeWorkers);
    return results;
  }

  private async runSingleProject(cwd: string, projectRelativePath: string): Promise<WorkspaceRunResult> {
    const projectDir = path.resolve(cwd, projectRelativePath);
    try {
      const config = await loadConfig(path.join(projectDir, ".loopforge.json"));
      const engine = new LoopEngine(config, projectDir);
      const result = await engine.runLoop(async () => `Executou ciclo no workspace: ${projectRelativePath}`);
      return { project: projectRelativePath, success: result.success };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      console.warn(chalk.yellow(`⚠️ [Workspace] Falha ao executar loop no projeto '${projectRelativePath}': ${errorMsg}`));
      return { project: projectRelativePath, success: false, error: errorMsg };
    }
  }
}
