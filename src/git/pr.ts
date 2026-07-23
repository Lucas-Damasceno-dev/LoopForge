import { exec } from "node:child_process";
import { promisify } from "node:util";
import type { LoopExecutionResult } from "../core/loop-engine.js";

const execAsync = promisify(exec);

export interface PRCreateOptions {
  title?: string;
  draft?: boolean;
  baseBranch?: string;
}

export async function isGitHubCLIInstalled(cwd: string = "."): Promise<boolean> {
  try {
    await execAsync("gh --version", { cwd });
    return true;
  } catch {
    return false;
  }
}

export async function createGitHubPullRequest(
  result: LoopExecutionResult,
  options: PRCreateOptions = {},
  cwd: string = "."
): Promise<{ success: boolean; url?: string; error?: string }> {
  if (!(await isGitHubCLIInstalled(cwd))) {
    return {
      success: false,
      error: "GitHub CLI ('gh') não está instalado no sistema. Instale para habilitar a criação automática de Pull Requests.",
    };
  }

  const title = options.title || `loopforge: automação concluída [${result.totalIterations} iterações]`;
  const isDraft = options.draft ? "--draft" : "";
  const baseBranch = options.baseBranch ? `--base "${options.baseBranch}"` : "";

  const prBody = generatePRBody(result);

  try {
    const command = `gh pr create --title "${title}" --body ${JSON.stringify(prBody)} ${isDraft} ${baseBranch}`;
    const { stdout } = await execAsync(command, { cwd });
    const url = stdout.trim();
    return { success: true, url };
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      error: msg || "Falha ao criar o Pull Request no GitHub.",
    };
  }
}

function generatePRBody(result: LoopExecutionResult): string {
  const runnerDetails = result.reports
    .map((r) => {
      const runnersList = r.harnessSummary.results
        .map((runner) => `- ${runner.passed ? "✅" : "❌"} **${runner.runnerName}** (${runner.type.toUpperCase()}) - ${runner.durationMs}ms`)
        .join("\n");
      return `### 🔄 Iteração #${r.iteration} [Modelo: ${r.modelUsed}]\n${runnersList}`;
    })
    .join("\n\n");

  return `# 🤖 LoopForge Automated Pull Request

> **Status Final**: ${result.success ? "✅ SUCESSO (Todos os sensores aprovados)" : "⚠️ CONCLUÍDO COM ALERTAS"}
> **Total de Iterações**: ${result.totalIterations} | **Tokens Consumidos**: ${result.totalTokensUsed} | **Custo Est.**: $${result.totalCostUsd.toFixed(4)}

---

## 📊 Relatório dos Sensores (Harness Execution)

${runnerDetails}

---

## 🛑 Motivo de Parada / Conclusão
${result.stopReason}

---

*Gerado automaticamente pelo [LoopForge Engine](https://github.com/Lucas-Damasceno-dev/LoopForge).*
`;
}
