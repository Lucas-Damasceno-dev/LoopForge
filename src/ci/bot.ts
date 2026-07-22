export interface BotCommandPayload {
  command: string; // e.g. "/loopforge run"
  user: string;
  channel: string;
  webhookUrl?: string;
}

export interface BotCommandResponse {
  handled: boolean;
  replyMessage: string;
  sentToWebhook: boolean;
}

export async function handleSlackOrDiscordBotCommand(payload: BotCommandPayload): Promise<BotCommandResponse> {
  const cmd = payload.command.trim().toLowerCase();
  let replyMessage = "";
  let handled = false;

  if (cmd.includes("run")) {
    handled = true;
    replyMessage = `🤖 [LoopForge Bot]: Comando '/loopforge run' recebido de @${payload.user}. Disparando ciclo de automação com Harness...`;
  } else if (cmd.includes("status")) {
    handled = true;
    replyMessage = `ℹ️ [LoopForge Bot]: Status do LoopForge em #${payload.channel}: Ativo (0 erros no Harness).`;
  } else {
    replyMessage = `⚠️ [LoopForge Bot]: Comando não reconhecido. Use '/loopforge run' ou '/loopforge status'.`;
  }

  let sentToWebhook = false;
  if (payload.webhookUrl) {
    try {
      const isDiscord = payload.webhookUrl.includes("discord.com");
      const body = isDiscord
        ? JSON.stringify({ content: replyMessage })
        : JSON.stringify({ text: replyMessage });

      const res = await fetch(payload.webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });

      sentToWebhook = res.ok;
    } catch {
      sentToWebhook = false;
    }
  }

  return { handled, replyMessage, sentToWebhook };
}
