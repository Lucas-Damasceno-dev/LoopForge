import { describe, it, expect } from "vitest";
import { handleSlackOrDiscordBotCommand } from "../src/ci/bot.js";

describe("LoopForge Slack & Discord Bot Handler", () => {
  it("deve processar comando /loopforge run", () => {
    const res = handleSlackOrDiscordBotCommand({
      command: "/loopforge run",
      user: "lucasd",
      channel: "dev-team",
    });

    expect(res.handled).toBe(true);
    expect(res.replyMessage).toContain("run");
  });
});
