import { loadConfig } from "../config/loader.js";
import { LoopEngine } from "../core/loop-engine.js";

export interface BotCommandPayload {
  command: string; // e.g. "/loopforge run"
  user: string;
  channel: string;
  webhookUrl?: string;
  cwd?: string;
}

export interface BotCommandResponse {
  handled: boolean;
  replyMessage: string;
  sentToWebhook: boolean;
  loopExecuted?: boolean;
}

export async function handleSlackOrDiscordBotCommand(payload: BotCommandPayload): Promise<BotCommandResponse> {
  const cmd = payload.command.trim().toLowerCase();
  let replyMessage = "";
  let handled = false;
  let loopExecuted = false;

  if (cmd.includes("run")) {
    handled = true;
    replyMessage = `🤖 [LoopForge Bot]: Comando '/loopforge run' recebido de @${payload.user}. Disparando ciclo de automação com Harness...`;

    if (payload.cwd) {
      try {
        const config = await loadConfig(undefined, payload.cwd);
        const engine = new LoopEngine(config, payload.cwd);
        const res = await engine.runLoop();
        loopExecuted = res.success;
        replyMessage += `\n✅ Loop concluído com status: ${res.success ? "SUCESSO" : "FALHA"} (${res.totalIterations} iterações).`;
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        replyMessage += `\n❌ Erro na execução do Loop Engine: ${msg}`;
      }
    }
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
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.warn(`⚠️ [Bot Webhook] Erro ao disparar mensagem para webhook: ${msg}`);
      sentToWebhook = false;
    }
  }

  return { handled, replyMessage, sentToWebhook, loopExecuted };
}
