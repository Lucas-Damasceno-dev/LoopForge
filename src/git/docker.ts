import { execFile, exec } from "node:child_process";
import { promisify } from "node:util";
import chalk from "chalk";

const execAsync = promisify(exec);
const execFileAsync = promisify(execFile);

export async function isDockerAvailable(): Promise<boolean> {
  try {
    await execAsync("docker --version");
    return true;
  } catch {
    return false;
  }
}

export async function runInDockerContainer(
  command: string,
  targetDir: string = ".",
  options: { image?: string } = {}
): Promise<{ success: boolean; output: string; usedFallback: boolean }> {
  const image = options.image || "node:20-alpine";
  const isAvail = await isDockerAvailable();

  if (!isAvail) {
    console.warn(chalk.yellow(`⚠️ Docker não está instalado ou rodando. Executando fallback localmente no host...`));
    try {
      const { stdout, stderr } = await execAsync(command, { cwd: targetDir });
      return { success: true, output: `${stdout}\n${stderr}`, usedFallback: true };
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      return { success: false, output: errorMsg, usedFallback: true };
    }
  }

  try {
    // Use execFile to prevent shell injection vulnerabilities
    const args = ["run", "--rm", "-v", `${targetDir}:/app`, "-w", "/app", image, "sh", "-c", command];
    const { stdout, stderr } = await execFileAsync("docker", args);
    return { success: true, output: `${stdout}\n${stderr}`, usedFallback: false };
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return { success: false, output: errorMsg, usedFallback: false };
  }
}
