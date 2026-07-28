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
    const safeMessage = message.replace(/"/g, '\\"');
    await execAsync(`git add -A`, { cwd });
    await execAsync(`git commit -m "${safeMessage} (${tag})"`, { cwd });
    return tag;
  } catch {
    return "";
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

export async function getWorkingDiff(cwd: string = "."): Promise<string> {
  if (!(await isGitRepo(cwd))) return "";
  try {
    const { stdout } = await execAsync("git diff --unified=5", { cwd });
    return stdout.trim();
  } catch {
    return "";
  }
}

export async function cleanupOldCheckpoints(cwd: string = "."): Promise<number> {
  if (!(await isGitRepo(cwd))) return 0;
  try {
    let cleaned = 0;
    // 1. Clean up git stashes matching loopforge-ckpt-
    const { stdout: stashOut } = await execAsync("git stash list", { cwd }).catch(() => ({ stdout: "" }));
    const stashLines = stashOut.split("\n").filter((l) => l.includes("loopforge-ckpt-"));

    const indices: number[] = [];
    for (const line of stashLines) {
      const match = line.match(/stash@\{(\d+)\}/);
      if (match) {
        indices.push(parseInt(match[1], 10));
      }
    }
    indices.sort((a, b) => b - a);
    for (const index of indices) {
      await execAsync(`git stash drop stash@{${index}}`, { cwd }).catch(() => {
        /* ignore error */
      });
      cleaned++;
    }

    // 2. Count checkpoint commits in git log
    const { stdout: logOut } = await execAsync("git log --oneline --grep=loopforge-ckpt-", { cwd }).catch(() => ({ stdout: "" }));
    const commitLines = logOut.split("\n").filter(Boolean);
    cleaned += commitLines.length;

    return cleaned;
  } catch {
    return 0;
  }
}
