import * as path from "node:path";
import { startWebUIServer } from "../../ui/server.js";

export async function uiCommand(targetDir: string = ".", options: { port?: string } = {}): Promise<void> {
  const resolvedDir = path.resolve(targetDir);
  const port = options.port ? parseInt(options.port, 10) : 3000;

  await startWebUIServer(port, resolvedDir);
}
