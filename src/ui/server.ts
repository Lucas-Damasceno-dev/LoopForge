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
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }
    h1 { color: #38bdf8; font-size: 1.8rem; margin-top: 0; }
    .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-weight: bold; font-size: 0.85rem; }
    .badge-success { background: #059669; color: #fff; }
    .metric { font-size: 2rem; font-weight: bold; color: #a7f3d0; margin: 0.5rem 0; }

        console.warn('Dashboard report load error:', e);
      }
    }
    loadReport();

    const ws = new WebSocket('ws://' + window.location.host);
    ws.onmessage = (event) => {
      const feed = document.getElementById('liveFeed');
      const item = document.createElement('div');
      item.innerText = '[' + new Date().toLocaleTimeString() + '] ' + event.data;
      feed.prepend(item);
    };
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
