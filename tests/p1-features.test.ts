import { describe, it, expect, beforeEach, afterEach } from "vitest";
import * as fs from "node:fs/promises";
import * as path from "node:path";
import * as os from "node:os";
import { CodeIndexer, cosineSimilarity } from "../src/indexer/rag.js";
import { TelemetryStore } from "../src/telemetry/store.js";
import { sendMultiChannelNotification } from "../src/ci/notifications/index.js";
import { SecurityScanner } from "../src/guardrails/security-scanner.js";
import { WorkspaceOrchestrator } from "../src/core/workspace.js";
import { CircuitBreaker } from "../src/guardrails/circuit-breaker.js";
import { generateAnalyticsReport } from "../src/telemetry/analytics.js";
import { TestGenerator } from "../src/harness/test-generator.js";

describe("LoopForge P1 Proposals Verification", () => {
  let tmpDir: string;

  beforeEach(async () => {
    tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "loopforge-p1-test-"));
  });

  afterEach(async () => {
    await fs.rm(tmpDir, { recursive: true, force: true });
  });

  it("1. RAG Semântico: deve calcular cosine similarity e indexar símbolos", async () => {
    const sim = cosineSimilarity([1, 0, 0], [1, 0, 0]);
    expect(sim).toBe(1);

    const codeFile = path.join(tmpDir, "sample.ts");
    await fs.writeFile(codeFile, `export function testFunction() { return 42; }`);
    const indexer = new CodeIndexer(".loopforge/index");
    const count = await indexer.indexRepository(tmpDir);
    expect(count).toBeGreaterThan(0);

    const matches = await indexer.searchRelevantSnippets("testFunction", 1, tmpDir);
    expect(matches.length).toBeGreaterThan(0);
    expect(matches[0].name).toBe("testFunction");
  });

  it("2. Telemetria Persistente SQLite: deve gravar e consultar sessões e gráfico de tendências", async () => {
    const store = await TelemetryStore.getInstance(tmpDir);
    const id = store.recordSession(
      {
        projectName: "TestProj",
        timestamp: new Date().toISOString(),
        totalIterations: 2,
        totalTokensUsed: 500,
        totalCostUsd: 0.05,
        success: true,
        stopReason: "Completed",
      },
      [
        { iteration: 1, passed: true, modelUsed: "deepseek-v3", tokensUsed: 250, costUsd: 0.025 },
        { iteration: 2, passed: true, modelUsed: "deepseek-v3", tokensUsed: 250, costUsd: 0.025 },
      ]
    );

    expect(id).toBeGreaterThan(0);
    const sessions = store.getAllSessions();
    expect(sessions.length).toBe(1);
    expect(sessions[0].totalCostUsd).toBe(0.05);

    const costTrend = store.getCostTrend();
    expect(costTrend.length).toBe(1);

    store.close();
  });

  it("5. Notificações Multi-canal: deve responder adequadamente a envio de notificações", async () => {
    const res = await sendMultiChannelNotification(
      { desktop: { enabled: true } },
      { title: "Test Notification", message: "Unit Test", status: "success" }
    );
    expect(res.desktop).toBe(true);
  });

  it("7. Security Auto-Fix: deve mover secrets para .env e substituir eval()", async () => {
    const insecureFile = path.join(tmpDir, "vulnerable.ts");
    await fs.writeFile(
      insecureFile,
      `const secret = "sk-12345678901234567890123456789012";\nconst val = eval("1+1");`
    );

    const scanner = new SecurityScanner();
    const vulns = await scanner.scanDirectory(tmpDir);
    expect(vulns.length).toBe(2);

    const fixRes = await scanner.autoFixVulnerabilities(tmpDir, vulns);
    expect(fixRes.fixedCount).toBe(2);

    const updatedContent = await fs.readFile(insecureFile, "utf-8");
    expect(updatedContent).toContain("process.env.LOOPFORGE_SECRET_VAR_1");
    expect(updatedContent).toContain("JSON.parse");

    const envContent = await fs.readFile(path.join(tmpDir, ".env"), "utf-8");
    expect(envContent).toContain("LOOPFORGE_SECRET_VAR_1=sk-12345678901234567890123456789012");
  });

  it("8. Execução Paralela de Workspaces: deve rodar projetos em paralelo", async () => {
    const proj1 = path.join(tmpDir, "proj1");
    const proj2 = path.join(tmpDir, "proj2");
    await fs.mkdir(proj1, { recursive: true });
    await fs.mkdir(proj2, { recursive: true });

    await fs.writeFile(
      path.join(proj1, ".loopforge.json"),
      JSON.stringify({ projectName: "p1", harness: { runners: [{ name: "test", type: "unit", command: "echo 1" }] } })
    );
    await fs.writeFile(
      path.join(proj2, ".loopforge.json"),
      JSON.stringify({ projectName: "p2", harness: { runners: [{ name: "test", type: "unit", command: "echo 1" }] } })
    );

    const manifest = path.join(tmpDir, "loopforge-workspace.json");
    await fs.writeFile(manifest, JSON.stringify({ projects: ["proj1", "proj2"] }));

    const orchestrator = new WorkspaceOrchestrator("loopforge-workspace.json");
    const results = await orchestrator.runWorkspaceLoops(tmpDir, { parallel: true, concurrency: 2 });
    expect(results.length).toBe(2);
    expect(results.every((r) => r.success)).toBe(true);
  });

  it("9. Budget por Iteração: deve disparar limite se a iteração exceder maxCostPerIteration", async () => {
    const cb = new CircuitBreaker({ maxCostPerIteration: 0.1 });
    const status = cb.recordSuccess(0.5);
    expect(status.isOpen).toBe(true);
    expect(status.reason).toContain("Custo por iteração excedeu o limite");
  });

  it("6. Multi-stack Test Generator: deve gerar testes no formato Python/pytest se detectado pyproject.toml", async () => {
    await fs.writeFile(path.join(tmpDir, "pyproject.toml"), "[tool.poetry]\nname = 'demo'");
    await fs.writeFile(path.join(tmpDir, "auth.py"), "def login(): return True");

    const generator = new TestGenerator();
    const results = await generator.generateTestsForUncoveredCode(tmpDir, false);
    expect(results.length).toBe(1);
    expect(results[0].testFile).toContain("test_auth.py");
  });
});
