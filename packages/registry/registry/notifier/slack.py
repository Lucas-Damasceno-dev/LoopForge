"""Notificador de Webhook Slack para quebras de contrato."""

from typing import List
import requests
from registry.notifier.base import BaseNotifier
from registry.store.models import BreakingChange


class SlackNotifier(BaseNotifier):
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def notify(self, breaking_changes: List[BreakingChange]) -> None:
        if not breaking_changes or not self.webhook_url:
            return

        text_lines = [f"🚨 *Agentic Registry Alert*: {len(breaking_changes)} Breaking Changes Detectadas!"]
        for bc in breaking_changes:
            text_lines.append(f"• `{bc.interface_name}` em `{bc.module}` ({bc.change_type}): {bc.details}")

        payload = {"text": "\n".join(text_lines)}
        try:
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception:
            pass
