import * as fs from "node:fs/promises";
import * as path from "node:path";
import chalk from "chalk";
import { TelemetryStore } from "./store.js";

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

  const store = await TelemetryStore.getInstance(resolvedDir);

  try {
    const raw = await fs.readFile(reportPath, "utf-8");
    const json = JSON.parse(raw);

    if (json && json.reports) {
      store.recordSession(
        {
          projectName: json.projectName || "LoopForge Project",
          timestamp: new Date().toISOString(),
          totalIterations: json.totalIterations || 0,
          totalTokensUsed: json.totalTokensUsed || 0,
          totalCostUsd: json.totalCostUsd || 0,
          success: json.success ?? true,
          stopReason: json.stopReason || "Concluído",
        },
        json.reports.map((r: any) => ({
          iteration: r.iteration,
          passed: r.passed,
          modelUsed: r.modelUsed || "default",
          tokensUsed: r.tokensUsed || 0,
          costUsd: r.estimatedCostUsd || 0,
        }))
      );
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(chalk.yellow(`ℹ️ [Analytics] Sincronização do report.json: ${msg}`));
  }

  const sessions = store.getAllSessions();
  const costTrend = store.getCostTrend();
  const passRateTrend = store.getPassRateTrend();

  const totalSessions = sessions.length || 1;
  const totalIterations = sessions.reduce((acc, s) => acc + s.totalIterations, 0);
  const totalTokensUsed = sessions.reduce((acc, s) => acc + s.totalTokensUsed, 0);
  const totalCostUsd = sessions.reduce((acc, s) => acc + s.totalCostUsd, 0);
  const successfulSessions = sessions.filter((s) => s.success).length;
  const passRatePercent = sessions.length > 0 ? Math.round((successfulSessions / sessions.length) * 100) : 100;

  const summary: AnalyticsSummary = {
    totalSessions,
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
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem; }
    .metric-card { background: #1e293b; padding: 1.5rem; border-radius: 10px; border: 1px solid #334155; }
    .val { font-size: 2rem; font-weight: bold; color: #38bdf8; }
    .chart-card { background: #1e293b; padding: 1.5rem; border-radius: 10px; border: 1px solid #334155; margin-top: 1.5rem; }
  </style>
</head>
<body>
  <h1>📊 Relatório de Telemetria SQLite e Tendências - LoopForge</h1>
  <div class="grid">
    <div class="metric-card"><div>Sessões Gravadas</div><div class="val">${summary.totalSessions}</div></div>
    <div class="metric-card"><div>Iterações Totais</div><div class="val">${summary.totalIterations}</div></div>
    <div class="metric-card"><div>Tokens Consumidos</div><div class="val">${summary.totalTokensUsed}</div></div>
    <div class="metric-card"><div>Custo Acumulado (USD)</div><div class="val">$${summary.totalCostUsd.toFixed(4)}</div></div>
    <div class="metric-card"><div>Taxa de Sucesso</div><div class="val">${summary.passRatePercent}%</div></div>
  </div>

  <div class="chart-card">
    <h2>📈 Custo ao Longo do Tempo (USD)</h2>
    <canvas id="costChart" height="80"></canvas>
  </div>

  <div class="chart-card">
    <h2>🎯 Tendência de Pass Rate (%)</h2>
    <canvas id="passRateChart" height="80"></canvas>
  </div>

  <script>
    const costData = ${JSON.stringify(costTrend)};
    const passRateData = ${JSON.stringify(passRateTrend)};

    new Chart(document.getElementById('costChart'), {
      type: 'line',
      data: {
        labels: costData.map((d, i) => 'Sessão #' + (i + 1)),
        datasets: [{
          label: 'Custo Total (USD)',
          data: costData.map(d => d.costUsd),
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          fill: true
        }]
      }
    });

    new Chart(document.getElementById('passRateChart'), {
      type: 'line',
      data: {
        labels: passRateData.map((d, i) => 'Sessão #' + (i + 1)),
        datasets: [{
          label: 'Pass Rate (%)',
          data: passRateData.map(d => d.passRate),
          borderColor: '#4ade80',
          backgroundColor: 'rgba(74, 222, 128, 0.1)',
          fill: true
        }]
      }
    });
  </script>
</body>
</html>`;

  await fs.mkdir(path.dirname(htmlPath), { recursive: true });
  await fs.writeFile(htmlPath, html, "utf-8");

  store.close();
  return { summary, reportHtmlPath: htmlPath };
}
