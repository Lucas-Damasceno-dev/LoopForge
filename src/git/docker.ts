import { exec } from "node:child_process";
import { promisify } from "node:util";

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
): Promise<{ success: boolean; output: string }> {
  try {
    const isAvail = await isDockerAvailable();
    if (!isAvail) {
      return { success: false, output: "Docker CLI não está disponível no sistema." };
    }

    const { stdout, stderr } = await execAsync(`docker run --rm -v "${cwd}:/app" -w /app ${image} ${command}`);
    return { success: true, output: `${stdout}\n${stderr}` };
  } catch (err: any) {
    return { success: false, output: err.message };
  }
}
