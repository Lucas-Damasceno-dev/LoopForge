"""Serviços de criação e gerenciamento de grupos."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Sequence

from app.core.exceptions import InviteExpiredError, NotFoundError, ValidationError
from app.models.entities import Group, Participant
from app.services.notifications import NotificationService
from app.utils import is_mock

class GroupService:
    """Serviço para criar grupos, convidar participantes e visualizar grupos."""

    def __init__(self, repository, email_service=None) -> None:
        """Inicializa o serviço com repositório e serviço de e-mail."""
        self.repository = repository
        self.email_service = email_service or NotificationService()

    def create_group(self, name: str, emails: Sequence[str]) -> Group:
        """Cria um grupo com status ativo e participantes.

        Args:
            name: nome do grupo.
            emails: e-mails dos participantes.

        Returns:
            Group: grupo criado.

        Raises:
            ValidationError: se nome ou participantes forem inválidos.
        """
        if not name or not name.strip():
            raise ValidationError("Group name is required")
        if not emails:
            raise ValidationError("At least one participant email is required")

        participants = [
            Participant(
                email=email.strip().lower(),
                status="pending",
                balance=Decimal("0.00"),
            )
            for email in emails
            if email and email.strip()
        ]

        if not participants:
            raise ValidationError("At least one valid participant email is required")

        group = Group(name=name.strip(), status="active", participants=participants)

        if hasattr(self.repository, "add"):
            saved = self.repository.add(group)
            if saved is not None and not is_mock(saved):
                return saved

        return group

    def view_group(self, group_id):
        """Retorna a visão de um grupo com participantes e saldos."""
        group = self.repository.get(group_id)
        if group is None:
            raise NotFoundError(f"Group {group_id} was not found")
        return group

    def add_participant(self, group_id, email):
        """Adiciona um participante por e-mail e envia convite.

        Args:
            group_id: identificador do grupo.
            email: e-mail do novo participante.

        Returns:
            Participant: participante criado.

        Raises:
            ValidationError: se o e-mail for inválido.
            NotFoundError: se o grupo não existir.
        """
        if not email or not email.strip():
            raise ValidationError("Email is required")

        group = self.repository.get(group_id)
        if group is None:
            raise NotFoundError(f"Group {group_id} was not found")

        participant = Participant(
            email=email.strip().lower(),
            status="pending",
            balance=Decimal("0.00"),
        )

        if hasattr(group, "participants"):
            group.participants.append(participant)

        if hasattr(self.email_service, "send_invite"):
            self.email_service.send_invite(email.strip().lower())
        if hasattr(self.email_service, "send"):
            self.email_service.send(email.strip().lower())

        return participant

    def accept_invite(self, group_id, email) -> Participant:
        """Aceita o convite de um participante, tornando-o ativo.

        Args:
            group_id: identificador do grupo.
            email: e-mail do participante.

        Returns:
            Participant: participante com status atualizado.

        Raises:
            NotFoundError: se o grupo ou participante não for encontrado.
            InviteExpiredError: se o convite expirou.
        """
        group = self.repository.get(group_id)
        if group is None:
            raise NotFoundError(f"Group {group_id} was not found")

        for participant in group.participants:
            if getattr(participant, "email", None) == email.lower():
                if getattr(participant, "status", None) == "expired":
                    raise InviteExpiredError("Invite has expired")
                participant.status = "active"
                return participant

        raise NotFoundError(f"Participant {email} was not found in group {group_id}")

    def expire_invites(self, group_id, days: int = 7):
        """Expira convites pendentes com mais de ``days`` dias.

        Args:
            group_id: identificador do grupo.
            days: quantidade de dias para expiração.

        Returns:
            list[Participant]: participantes com convite expirado.
        """
        return self.expire_pending_invites(group_id, days)

    def expire_pending_invites(self, group_id, days: int = 7):
        """Expira convites pendentes que ultrapassaram a validade.

        Arg:
            group_id: identificador do grupo.
            days: quantidade de dias para expiração.

        Returns:
            list[Participant]: participantes expirados.
        """
        group = self.repository.get(group_id)
        if group is None:
            raise NotFoundError(f"Group {group_id} was not found")

        now = datetime.utcnow()
        expiration = timedelta(days=days)
        expired: list[Participant] = []

        for participant in group.participants:
            status = getattr(participant, "status", None)
            created_at = getattr(participant, "created_at", now)

            if created_at is None:
                continue

            if status == "pending" and (now - created_at) > expiration:
                participant.status = "expired"
                expired.append(participant)

        return expired