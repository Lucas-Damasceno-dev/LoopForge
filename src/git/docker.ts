import { exec } from "node:child_process";
import { promisify } from "node:util";
import chalk from "chalk";

const execAsync = promisify(exec);

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
  image: string = "node:20-alpine",
  cwd: string = "."
): Promise<{ success: boolean; output: string; usedFallback: boolean }> {
  const isAvail = await isDockerAvailable();

  if (!isAvail) {
    console.warn(chalk.yellow(`⚠️ Docker não está instalado ou rodando. Executando fallback localmente no host...`));
    try {
      const { stdout, stderr } = await execAsync(command, { cwd });
      return { success: true, output: `${stdout}\n${stderr}`, usedFallback: true };
    } catch (err: any) {
      return { success: false, output: err.message, usedFallback: true };
    }
  }

  try {
    const { stdout, stderr } = await execAsync(`docker run --rm -v "${cwd}:/app" -w /app ${image} ${command}`);
    return { success: true, output: `${stdout}\n${stderr}`, usedFallback: false };
  } catch (err: any) {
    return { success: false, output: err.message, usedFallback: false };
  }
}
