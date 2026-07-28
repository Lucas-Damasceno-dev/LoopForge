import { describe, it, expect } from "vitest";
import { isGitHubCLIInstalled } from "../src/git/pr.js";

describe("LoopForge GitHub PR Integration", () => {
  it("deve verificar se o GitHub CLI (gh) está disponível no sistema", async () => {
    const installed = await isGitHubCLIInstalled();
    expect(typeof installed).toBe("boolean");
  });
});
