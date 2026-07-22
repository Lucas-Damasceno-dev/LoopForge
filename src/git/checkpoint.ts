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

export async function createCheckpoint(message: string, cwd: string = "."): Promise<string> {
  if (!(await isGitRepo(cwd))) return "";
  try {
    const timestamp = Date.now();
    const tag = `loopforge-ckpt-${timestamp}`;
    await execAsync(`git stash push -m "${message} (${tag})"`, { cwd });
    return tag;
  } catch {
    return "";
  }
}

export async function rollbackToCheckpoint(cwd: string = "."): Promise<boolean> {
  if (!(await isGitRepo(cwd))) return false;
  try {
    await execAsync("git stash pop", { cwd });
    return true;
  } catch {
    return false;
  }
}

export async function cleanupOldCheckpoints(cwd: string = "."): Promise<number> {
  if (!(await isGitRepo(cwd))) return 0;
  try {
    const { stdout } = await execAsync("git stash list", { cwd });
    const lines = stdout.split("\n").filter((l) => l.includes("loopforge-ckpt-"));

    const indices: number[] = [];
    for (const line of lines) {
      const match = line.match(/stash@\{(\d+)\}/);
      if (match) {
        indices.push(parseInt(match[1], 10));
      }
    }

    // Sort indices descending so dropping higher indices doesn't shift lower indices
    indices.sort((a, b) => b - a);

    let cleaned = 0;
    for (const index of indices) {
      await execAsync(`git stash drop stash@{${index}}`, { cwd }).catch(() => {});
      cleaned++;
    }

    return cleaned;
  } catch {
    return 0;
  }
}
