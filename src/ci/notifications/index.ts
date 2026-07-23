import notifier from "node-notifier";
import nodemailer from "nodemailer";
import type { NotificationConfig } from "../../config/schema.js";

export interface NotificationPayload {
  title: string;
  message: string;
  status: "success" | "failure" | "breaker";
}

export async function sendMultiChannelNotification(
  config: NotificationConfig | undefined,
  payload: NotificationPayload
): Promise<{ webhook: boolean; email: boolean; desktop: boolean }> {
  const results = { webhook: false, email: false, desktop: false };

  if (!config) return results;

  // 1. Webhook Notification
  if (config.webhookUrl) {
    try {
      const body = JSON.stringify({
        username: "LoopForge Notification Bot",
        content: `**[${payload.title}]** (${payload.status.toUpperCase()})\n${payload.message}`,
      });
      await fetch(config.webhookUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
      });
      results.webhook = true;
    } catch {}
  }

  // 2. Desktop Notification
  if (config.desktop?.enabled !== false) {
    try {
      notifier.notify({
        title: `LoopForge: ${payload.title}`,
        message: payload.message,
        sound: payload.status === "failure" || payload.status === "breaker",
      });
      results.desktop = true;
    } catch {}
  }

  // 3. Email Notification
  if (config.email?.enabled && config.email.smtpHost && config.email.to) {
    try {
      const transporter = nodemailer.createTransport({
        host: config.email.smtpHost,
        port: config.email.smtpPort || 587,
        secure: (config.email.smtpPort || 587) === 465,
        auth: config.email.smtpUser
          ? {
              user: config.email.smtpUser,
              pass: config.email.smtpPass || "",
            }
          : undefined,
      });

      await transporter.sendMail({
        from: config.email.from || "loopforge@local.dev",
        to: config.email.to,
        subject: `[LoopForge ${payload.status.toUpperCase()}] ${payload.title}`,
        text: payload.message,
      });
      results.email = true;
    } catch {}
  }

  return results;
}
