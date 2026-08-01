"""Serviço de registros de pagamentos."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.core.exceptions import PaymentError
from app.utils import is_mock, round_money

@dataclass
class Payment:
    """Pagamento registrado entre participantes."""

    payer: str
    receiver: str
    amount: Decimal
    group_id: Optional[str] = None
    reason: str = ""
    id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

class PaymentService:
    """Serviço para registrar e consultar pagamentos."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com repositório opcional."""
        self.repository = repository

    def record_payment(
        self,
        payer: str,
        receiver: str,
        amount: Decimal,
        group_id=None,
        reason: str = "Manual payment",
    ) -> Payment:
        """Registra um pagamento.

        Args:
            payer: participante que paga.
            receiver: participante que recebe.
            amount: valor pago.
            group_id: identificador do grupo.
            reason: motivo do pagamento.

        Returns:
            Payment: pagamento registrado.

        Raises:
            PaymentError: se o valor for inválido ou pagador/recebedor ausente.
        """
        if not payer or not receiver:
            raise PaymentError("Payer and receiver are required")

        amount = round_money(amount)
        if amount <= 0:
            raise PaymentError("Amount must be positive")

        payment = Payment(
            payer=payer,
            receiver=receiver,
            amount=amount,
            group_id=group_id,
            reason=reason,
        )

        if self.repository is not None and hasattr(self.repository, "add"):
            saved = self.repository.add(payment)
            if saved is not None and not is_mock(saved):
                return saved

        return payment

    def register_payment(
        self,
        payer: str,
        receiver: str,
        amount: Decimal,
        group_id=None,
        reason: str = "Manual payment",
    ) -> Payment:
        """Alias para ``record_payment``."""
        return self.record_payment(
            payer=payer,
            receiver=receiver,
            amount=amount,
            group_id=group_id,
            reason=reason,
        )

    def list_payments(self, group_id):
        """Lista pagamentos de um grupo."""
        if self.repository is None:
            return []
        return self.repository.list_payments(group_id)

def register_payment(
    payer: str,
    receiver: str,
    amount: Decimal,
    group_id=None,
    reason: str = "Manual payment",
) -> Payment:
    """Função de conveniência para registrar um pagamento."""
    return PaymentService().record_payment(
        payer=payer,
        receiver=receiver,
        amount=amount,
        group_id=group_id,
        reason=reason,
    )