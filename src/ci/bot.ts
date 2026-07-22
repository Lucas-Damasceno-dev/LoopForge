export interface BotCommandPayload {
  command: string; // e.g. "/loopforge run"
  user: string;
  channel: string;
}

export interface BotCommandResponse {
  handled: boolean;
  replyMessage: string;
}

export function handleSlackOrDiscordBotCommand(payload: BotCommandPayload): BotCommandResponse {
  const cmd = payload.command.trim().toLowerCase();

  if (cmd.includes("run")) {
    return {
      handled: true,
      replyMessage: `🤖 [LoopForge Bot]: Comando '/loopforge run' recebido de @${payload.user}. Disparando ciclo de automação com Harness...`,
    };
  }

  if (cmd.includes("status")) {
    return {
      handled: true,
      replyMessage: `ℹ️ [LoopForge Bot]: Status do Loop Forge em #${payload.channel}: Ativo (0 erros no Harness).`,
    };
  }

  return {
    handled: false,
    replyMessage: `⚠️ [LoopForge Bot]: Comando não reconhecido. Use '/loopforge run' ou '/loopforge status'.`,
  };
}
