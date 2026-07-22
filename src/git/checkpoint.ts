import { exec } from "node:child_process";
import { promisify } from "node:util";

const execAsync = promisify(exec);

export async function isGitRepo(cwd: string = "."): Promise<boolean> {
  try {
    await execAsync("git rev-parse --is-inside-work-tree", { cwd });
    return true;
  } catch {
    return false;
  }
}

export async function createCheckpoint(message: string, cwd: string = "."): Promise<boolean> {
  if (!(await isGitRepo(cwd))) return false;

  try {
    await execAsync("git add -A", { cwd });
    await execAsync(`git commit -m "loopforge: checkpoint - ${message}" --allow-empty`, { cwd });
    return true;
  } catch {
    return false;
  }
}

export async function rollbackToCheckpoint(cwd: string = "."): Promise<boolean> {
  if (!(await isGitRepo(cwd))) return false;

  try {
    await execAsync("git reset --hard HEAD", { cwd });
    await execAsync("git clean -fd", { cwd });
    return true;
  } catch {
    return false;
  }
}
