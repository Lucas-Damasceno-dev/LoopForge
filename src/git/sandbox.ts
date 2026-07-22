import { exec } from "node:child_process";
import { promisify } from "node:util";
import { isGitRepo } from "./checkpoint.js";

const execAsync = promisify(exec);

export interface SandboxInfo {
  sandboxBranch: string;
  originalBranch: string;
}

export async function getCurrentBranch(cwd: string = "."): Promise<string> {
  if (!(await isGitRepo(cwd))) return "main";
  try {
    const { stdout } = await execAsync("git rev-parse --abbrev-ref HEAD", { cwd });
    return stdout.trim();
  } catch {
    return "main";
  }
}

export async function createSandboxBranch(
  branchPrefix: string = "loopforge/task-",
  cwd: string = "."
): Promise<SandboxInfo | null> {
  if (!(await isGitRepo(cwd))) return null;

  try {
    const originalBranch = await getCurrentBranch(cwd);
    const timestamp = Date.now();
    const sandboxBranch = `${branchPrefix}${timestamp}`;

    await execAsync(`git checkout -b ${sandboxBranch}`, { cwd });
    return { sandboxBranch, originalBranch };
  } catch {
    return null;
  }
}

export async function mergeSandboxBranch(
  sandboxBranch: string,
  targetBranch: string,
  cwd: string = "."
): Promise<boolean> {
  if (!(await isGitRepo(cwd))) return false;

  try {
    await execAsync(`git checkout ${targetBranch}`, { cwd });
    await execAsync(`git merge ${sandboxBranch} --no-ff -m "loopforge: merge sandbox ${sandboxBranch}"`, { cwd });
    await execAsync(`git branch -d ${sandboxBranch}`, { cwd });
    return true;
  } catch {
    return false;
  }
}

export async function cleanupSandboxBranch(
  sandboxBranch: string,
  targetBranch: string,
  cwd: string = "."
): Promise<boolean> {
  if (!(await isGitRepo(cwd))) return false;

  try {
    await execAsync(`git checkout ${targetBranch}`, { cwd });
    await execAsync(`git branch -D ${sandboxBranch}`, { cwd });
    return true;
  } catch {
    return false;
  }
}
