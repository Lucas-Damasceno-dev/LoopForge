import { describe, it, expect } from "vitest";
import { WorkspaceOrchestrator } from "../src/core/workspace.js";

describe("LoopForge Workspace Orchestrator", () => {
  it("deve inicializar o orquestrador de workspace", () => {
    const orchestrator = new WorkspaceOrchestrator();
    expect(orchestrator).toBeDefined();
  });
});
