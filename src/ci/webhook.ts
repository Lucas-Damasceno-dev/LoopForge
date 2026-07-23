import * as fs from "node:fs/promises";
import * as path from "node:path";
import { sendMultiChannelNotification } from "./notifications/index.js";

export async function sendCIWebhookNotification(
  webhookUrl: string,
  payload: { title: string; message: string; status: "success" | "failure" | "breaker" }
): Promise<boolean> {
  const res = await sendMultiChannelNotification({ webhookUrl, desktop: { enabled: false } }, payload);
  return res.webhook;
}

export async function generateGitHubActionWorkflow(cwd: string = "."): Promise<string> {
  const resolvedDir = path.resolve(cwd);
  const workflowDir = path.join(resolvedDir, ".github/workflows");
  const workflowPath = path.join(workflowDir, "loopforge-ci.yml");

  const workflowYaml = `name: LoopForge Automated CI Loop

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  loopforge-verification:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci
      - name: CodeQL / Security Check
        run: npx loopforge audit
      - run: npx loopforge run --create-pr
`;

  await fs.mkdir(workflowDir, { recursive: true });
  await fs.writeFile(workflowPath, workflowYaml, "utf-8");

  return workflowPath;
}

export { sendMultiChannelNotification };
