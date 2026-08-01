"""Serviço de notificações e convites."""
from datetime import datetime

from app.config import settings
from app.core.exceptions import ValidationError

class NotificationService:
    """Responsável por enviar notificações e convites."""

    def __init__(self, sender: str = "") -> None:
        """Inicializa o serviço com o remetente padrão."""
        self.sender = sender or settings.email_sender

    def send_invite(self, email: str, group_id=None, invite_url: str | None = None) -> dict:
        """Envia um convite para o e-mail informado.

        Args:
            email: e-mail do destinatário.
            group_id: identificador opcional do grupo.
            invite_url: URL personalizada do convite.

        Returns:
            dict: payload da notificação enviada.

        Raises:
            ValidationError: se o e-mail for vazio.
        """
        if not email or not email.strip():
            raise ValidationError("Email is required to send invitation")

        if invite_url:
            url = invite_url
        elif group_id:
            url = f"https://{settings.app_name}/invite/{group_id}"
        else:
            url = "https://example.com/invite"

        return {
            "to": email.strip().lower(),
            "type": "invite",
            "url": url,
            "sender": self.sender,
            "sent_at": datetime.utcnow(),
        }

    def send_settlement_notification(self, recipient: str, message: str) -> dict:
        """Envia uma notificação de liquidação para um participante.

        Args:
            recipient: destinatário da notificação.
            message: mensagem da notificação.

        Returns:
            dict: payload da notificação enviada.

        Raises:
            ValidationError: se o destinatário for vazio.
        """
        if not recipient or not recipient.strip():
            raise ValidationError("Recipient is required")

        return {
            "to": recipient.strip(),
            "message": message,
            "sent_at": datetime.utcnow(),
        }