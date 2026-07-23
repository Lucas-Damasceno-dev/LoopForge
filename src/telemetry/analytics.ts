import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";

export interface AnalyticsSummary {
  totalSessions: number;
  totalIterations: number;
  totalTokensUsed: number;
  totalCostUsd: number;
  passRatePercent: number;
}

export async function generateAnalyticsReport(cwd: string = "."): Promise<{ summary: AnalyticsSummary; reportHtmlPath: string }> {
  const resolvedDir = path.resolve(cwd);
  const reportPath = path.join(resolvedDir, ".loopforge/report.json");
  const htmlPath = path.join(resolvedDir, ".loopforge/analytics.html");

  let totalIterations = 0;
  let totalTokensUsed = 0;
  let totalCostUsd = 0;
  let passRatePercent = 100;

  try {
    const raw = await fs.readFile(reportPath, "utf-8");
    const json = JSON.parse(raw);
    totalIterations = json.totalIterations || 0;
    totalTokensUsed = json.totalTokensUsed || 0;
    totalCostUsd = json.totalCostUsd || 0;
    if (json.success === false) passRatePercent = 50;
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(chalk.yellow(`ℹ️ [Analytics] Relatório previo não encontrado (${msg}). Gerando relatório com métricas iniciais.`));
  }

  const summary: AnalyticsSummary = {
    totalSessions: 1,
    totalIterations,
    totalTokensUsed,
    totalCostUsd,
    passRatePercent,
  };

  const html = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>LoopForge Telemetry Analytics Report</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem; }
    .metric-card { background: #1e293b; padding: 1.5rem; border-radius: 10px; border: 1px solid #334155; }
    .val { font-size: 2rem; font-weight: bold; color: #38bdf8; }
  </style>
</head>
<body>
  <h1>📊 Relatório de Telemetria e Métricas - LoopForge</h1>
  <div class="grid">
    <div class="metric-card"><div>Iterações Totais</div><div class="val">${summary.totalIterations}</div></div>
    <div class="metric-card"><div>Tokens Consumidos</div><div class="val">${summary.totalTokensUsed}</div></div>
    <div class="metric-card"><div>Custo Acumulado (USD)</div><div class="val">$${summary.totalCostUsd.toFixed(4)}</div></div>
    <div class="metric-card"><div>Pass Rate dos Sensores</div><div class="val">${summary.passRatePercent}%</div></div>
  </div>
</body>
</html>`;

  await fs.mkdir(path.dirname(htmlPath), { recursive: true });
  await fs.writeFile(htmlPath, html, "utf-8");

  return { summary, reportHtmlPath: htmlPath };
}
