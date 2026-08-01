"""Entidades de domínio do divisor de despesas."""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

@dataclass
class Participant:
    """Participante de um grupo de despesas.

    Attributes:
        email: E-mail do participante.
        status: status do convite (pending, active, expired).
        balance: saldo calculado do participante.
        id: identificador único.
        group_id: identificador do grupo.
        name: nome opcional.
        created_at: data de criação.
    """

    email: str
    status: str = "pending"
    balance: Decimal = Decimal("0.00")
    id: Optional[str] = None
    group_id: Optional[str] = None
    name: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Group:
    """Grupo de despesas.

    Attributes:
        name: nome do grupo.
        status: status do grupo.
        participants: participantes do grupo.
        id: identificador único.
        created_at: data de criação.
    """

    name: str
    status: str = "active"
    participants: list[Participant] = field(default_factory=list)
    id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

@dataclass
class ExpenseSplit:
    """Divisão individual de uma despesa."""

    participant: str
    amount: Decimal

@dataclass
class Expense:
    """Despesa registrada em um grupo.

    Attributes:
        payer: participante que pagou a despesa.
        amount: valor total da despesa.
        splits: mapeamento de participante para valor devido.
        group_id: identificador do grupo.
        id: identificador único da despesa.
        description: descrição opcional.
        created_at: data de criação.
    """

    payer: str
    amount: Decimal
    splits: dict[str, Decimal] = field(default_factory=dict)
    group_id: Optional[str] = None
    id: Optional[str] = None
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_amount(self) -> Decimal:
        """Alias para o valor total da despesa."""
        return self.amount

    @property
    def total(self) -> Decimal:
        """Alias para o valor total da despesa."""
        return self.amount