import type { HarnessExecutionSummary } from "./types.js";

export function formatHarnessFeedback(summary: HarnessExecutionSummary): string {
  if (summary.allPassed) {
    return `### ✅ Sensor Status: TODOS OS TESTES PASSARAM (${summary.passedCount}/${summary.totalRunners} runners OK em ${summary.totalDurationMs}ms)`;
  }

  const failedRunners = summary.results.filter((r) => !r.passed);

  const failuresMarkdown = failedRunners
    .map((failed) => {
      const errorSnippet = failed.errorDetails || "Sem detalhes de erro.";
      return `#### ❌ Runner Falhou: ${failed.runnerName} (${failed.type.toUpperCase()})
- **Comando Executado**: \`${failed.command}\`
- **Duração**: ${failed.durationMs}ms
- **Código de Saída**: ${failed.exitCode ?? "N/A"}
\`\`\`text
${errorSnippet.trim()}
\`\`\``;
    })
    .join("\n\n");

  return `## 🚨 Diagnostic Harness Feedback (${summary.passedCount}/${summary.totalRunners} PASSANDO)

${failuresMarkdown}

> **Atenção Agentic Loop**: Corrija prioritariamente os erros apontados acima antes de avançar para novas funcionalidades.`;
}
