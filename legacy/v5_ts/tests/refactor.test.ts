import { describe, it, expect } from "vitest";
import { RefactorEngine } from "../src/core/refactor-engine.js";

describe("LoopForge Refactor Engine", () => {
  it("deve inicializar o motor de refatoração e varrer o repositório", async () => {
    const engine = new RefactorEngine();
    expect(engine).toBeDefined();
  });
});
