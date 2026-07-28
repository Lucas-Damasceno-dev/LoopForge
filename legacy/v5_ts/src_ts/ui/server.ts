import * as http from "node:http";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import { WebSocketServer, WebSocket } from "ws";
import chalk from "chalk";

export async function startWebUIServer(port: number = 3000, cwd: string = "."): Promise<{ server: http.Server; wss: WebSocketServer; broadcast: (msg: unknown) => void }> {
  const resolvedDir = path.resolve(cwd);

  const server = http.createServer(async (req, res) => {
    if (req.url === "/api/report") {
      try {
        const reportPath = path.join(resolvedDir, ".loopforge/report.json");
        const reportData = await fs.readFile(reportPath, "utf-8");
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(reportData);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        res.writeHead(404, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Nenhum relatório de execução encontrado.", details: msg }));
      }
      return;
    }

    if (req.url === "/api/telemetry/history") {
      try {
        const { TelemetryStore } = await import("../telemetry/store.js");
        const store = await TelemetryStore.getInstance(resolvedDir);
        const sessions = store.getAllSessions();
        const costTrend = store.getCostTrend();
        const passRateTrend = store.getPassRateTrend();
        store.close();
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ sessions, costTrend, passRateTrend }));
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Falha ao carregar histórico SQLite.", details: msg }));
      }
      return;
    }

    const htmlContent = `<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LoopForge Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0b0f19;
      --bg-secondary: #111827;
      --card-bg: #1f2937;
      --border-color: #374151;
      --accent-cyan: #38bdf8;
      --accent-purple: #a855f7;
      --success: #10b981;
      --danger: #ef4444;
      --warning: #f59e0b;
      --text-main: #f9fafb;
      --text-muted: #9ca3af;
    }

    * { box-sizing: border-box; }
    body {
      font-family: 'Inter', system-ui, -apple-system, sans-serif;
      background: var(--bg-primary);
      color: var(--text-main);
      margin: 0;
      padding: 0;
      line-height: 1.5;
    }

    header {
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border-color);
      padding: 1.25rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }

    .brand h1 {
      margin: 0;
      font-size: 1.5rem;
      font-weight: 700;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .header-status {
      display: flex;
      align-items: center;
      gap: 1rem;
    }

    .status-dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background: var(--warning);
      display: inline-block;
    }
    .status-dot.connected { background: var(--success); box-shadow: 0 0 8px var(--success); }

    .container {
      max-width: 1400px;
      margin: 2rem auto;
      padding: 0 1.5rem;
    }

    .grid-metrics {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.5rem;
      margin-bottom: 2rem;
    }

    .card {
      background: var(--card-bg);
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 1.5rem;
      transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .card:hover {
      border-color: #4b5563;
    }

    .metric-label {
      font-size: 0.875rem;
      color: var(--text-muted);
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .metric-value {
      font-size: 2rem;
      font-weight: 700;
      margin-top: 0.5rem;
      color: var(--text-main);
    }

    .metric-value.highlight { color: var(--accent-cyan); }
    .metric-value.success { color: var(--success); }

    .dashboard-layout {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 1.5rem;
    }

    @media (max-width: 1024px) {
      .dashboard-layout { grid-template-columns: 1fr; }
    }

    .section-title {
      font-size: 1.125rem;
      font-weight: 600;
      margin-top: 0;
      margin-bottom: 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }

    .live-feed {
      background: #0d1117;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.875rem;
      height: 380px;
      overflow-y: auto;
      display: flex;
      flex-direction: column-reverse;
      gap: 0.5rem;
    }

    .feed-item {
      padding: 0.35rem 0.6rem;
      border-radius: 4px;
      background: rgba(255, 255, 255, 0.03);
      word-break: break-word;
    }
    .feed-item .time { color: var(--text-muted); margin-right: 0.5rem; font-size: 0.75rem; }

    .badge {
      display: inline-block;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
    }
    .badge-success { background: rgba(16, 185, 129, 0.2); color: var(--success); border: 1px solid var(--success); }
    .badge-danger { background: rgba(239, 68, 68, 0.2); color: var(--danger); border: 1px solid var(--danger); }
    .badge-info { background: rgba(56, 189, 248, 0.2); color: var(--accent-cyan); border: 1px solid var(--accent-cyan); }

    .session-list {
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      max-height: 380px;
      overflow-y: auto;
    }

    .session-item {
      padding: 0.75rem 1rem;
      background: var(--bg-secondary);
      border-radius: 8px;
      border: 1px solid var(--border-color);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.875rem;
    }

    .diff-box {
      margin-top: 1.5rem;
      background: #0d1117;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 1rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.85rem;
      white-space: pre-wrap;
      max-height: 250px;
      overflow-y: auto;
      color: #c9d1d9;
    }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <h1>🚀 LoopForge Engine</h1>
      <span class="badge badge-info">v5.0.0</span>
    </div>
    <div class="header-status">
      <span class="status-dot" id="statusDot"></span>
      <span id="statusText" style="font-size:0.875rem; color:var(--text-muted)">Conectando...</span>
    </div>
  </header>

  <div class="container">
    <!-- Grid de Métricas Principais -->
    <div class="grid-metrics">
      <div class="card">
        <div class="metric-label">Status da Sessão</div>
        <div class="metric-value" id="sessionStatus">-</div>
      </div>
      <div class="card">
        <div class="metric-label">Iterações Executadas</div>
        <div class="metric-value highlight" id="totalIterations">0</div>
      </div>
      <div class="card">
        <div class="metric-label">Tokens Consumidos</div>
        <div class="metric-value" id="totalTokens">0</div>
      </div>
      <div class="card">
        <div class="metric-label">Custo Estimado (USD)</div>
        <div class="metric-value success" id="totalCost">$0.0000</div>
      </div>
    </div>

    <!-- Layout Principal -->
    <div class="dashboard-layout">
      <!-- Feed de Atividades ao Vivo -->
      <div class="card">
        <div class="section-title">
          <span>📡 Stream de Logs ao Vivo (WebSocket)</span>
          <span class="badge badge-info" id="feedCount">0 eventos</span>
        </div>
        <div class="live-feed" id="liveFeed">
          <div class="feed-item"><span class="time">--:--:--</span>Aguardando eventos do ciclo LoopForge...</div>
        </div>
      </div>

      <!-- Histórico de Telemetria SQLite -->
      <div class="card">
        <div class="section-title">
          <span>📊 Histórico de Telemetria (SQLite)</span>
        </div>
        <div class="session-list" id="sessionList">
          <div style="color:var(--text-muted); text-align:center; padding:1rem;">Carregando histórico...</div>
        </div>
      </div>
    </div>

    <!-- Detalhes do Relatório Ativo -->
    <div class="card" style="margin-top: 1.5rem;">
      <div class="section-title">
        <span>📄 Relatório da Última Execução</span>
        <span id="stopReason" style="font-size:0.875rem; font-weight:normal; color:var(--text-muted);"></span>
      </div>
      <div id="reportDetails" style="font-size:0.9rem; color:var(--text-muted);">Carregando .loopforge/report.json...</div>
      <div class="diff-box" id="diffViewer" style="display:none;"></div>
    </div>
  </div>

  <script>
    let logCounter = 0;

    async function loadReport() {
      try {
        const res = await fetch('/api/report');
        if (!res.ok) {
          document.getElementById('sessionStatus').innerHTML = '<span class="badge badge-info">IDLE</span>';
          document.getElementById('reportDetails').innerText = 'Nenhum relatório recente encontrado (.loopforge/report.json).';
          return;
        }
        const data = await res.json();
        
        const isSuccess = data.success;
        document.getElementById('sessionStatus').innerHTML = isSuccess 
          ? '<span class="badge badge-success">SUCESSO</span>' 
          : '<span class="badge badge-danger">INTERROMPIDO</span>';
        
        document.getElementById('totalIterations').innerText = data.totalIterations || 0;
        document.getElementById('totalTokens').innerText = (data.totalTokensUsed || 0).toLocaleString();
        document.getElementById('totalCost').innerText = '$' + (data.totalCostUsd || 0).toFixed(4);
        document.getElementById('stopReason').innerText = 'Motivo: ' + (data.stopReason || 'N/A');

        let html = '<strong>Total de relatórios de iteração:</strong> ' + (data.reports ? data.reports.length : 0) + '<br/>';
        if (data.sandboxBranchUsed) {
          html += '<strong>Branch Sandbox:</strong> <code>' + data.sandboxBranchUsed + '</code><br/>';
        }
        document.getElementById('reportDetails').innerHTML = html;

        const lastReport = data.reports && data.reports[data.reports.length - 1];
        if (lastReport && lastReport.diff) {
          const diffEl = document.getElementById('diffViewer');
          diffEl.style.display = 'block';
          diffEl.innerText = lastReport.diff;
        }
      } catch (e) {
        console.warn('Erro ao carregar relatório:', e);
      }
    }

    async function loadTelemetryHistory() {
      try {
        const res = await fetch('/api/telemetry/history');
        if (!res.ok) return;
        const data = await res.json();
        const container = document.getElementById('sessionList');
        if (!data.sessions || data.sessions.length === 0) {
          container.innerHTML = '<div style="color:var(--text-muted); text-align:center; padding:1rem;">Nenhuma sessão registrada.</div>';
          return;
        }
        container.innerHTML = data.sessions.slice(0, 10).map(s => {
          const statusBadge = s.success 
            ? '<span class="badge badge-success">PASS</span>' 
            : '<span class="badge badge-danger">FAIL</span>';
          const date = new Date(s.timestamp).toLocaleTimeString();
          return '<div class="session-item">' +
            '<div><strong>Iterações: ' + s.iterations + '</strong> <span style="color:var(--text-muted)">(' + date + ')</span></div>' +
            '<div>' + statusBadge + ' <span style="margin-left:0.5rem; color:var(--accent-cyan);">$'+ (s.costUsd || 0).toFixed(4) +'</span></div>' +
          '</div>';
        }).join('');
      } catch (e) {
        console.warn('Erro ao carregar telemetria:', e);
      }
    }

    function initWebSocket() {
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(wsProtocol + '//' + window.location.host);

      ws.onopen = () => {
        document.getElementById('statusDot').classList.add('connected');
        document.getElementById('statusText').innerText = 'Conectado (Ao Vivo)';
      };

      ws.onclose = () => {
        document.getElementById('statusDot').classList.remove('connected');
        document.getElementById('statusText').innerText = 'Desconectado (Reconectando...)';
        setTimeout(initWebSocket, 3000);
      };

      ws.onmessage = (event) => {
        logCounter++;
        document.getElementById('feedCount').innerText = logCounter + ' eventos';
        const feed = document.getElementById('liveFeed');
        const item = document.createElement('div');
        item.className = 'feed-item';
        const time = new Date().toLocaleTimeString();
        item.innerHTML = '<span class="time">[' + time + ']</span> ' + event.data;
        feed.prepend(item);
      };
    }

    loadReport();
    loadTelemetryHistory();
    initWebSocket();
  </script>
</body>
</html>`;

    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(htmlContent);
  });

  const wss = new WebSocketServer({ server });

  const broadcast = (msg: unknown) => {
    const payload = typeof msg === "string" ? msg : JSON.stringify(msg);
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(payload);
      }
    });
  };

  return new Promise((resolve) => {
    server.listen(port, () => {
      console.log(chalk.green(`\n🌐 LoopForge Web Dashboard rodando em: ${chalk.bold.cyan(`http://localhost:${port}`)} (WebSocket ativo)`));
      resolve({ server, wss, broadcast });
    });
  });
}
