"""Repositório em memória para testes e uso local."""

from __future__ import annotations

from app.core.exceptions import GroupNotFoundError
from app.models.entities import Expense, Group, Payment, Participant

class InMemoryRepository:
    """Repositório simples em memória.

    Mantém grupos, despesas e pagamentos em dicionários.
    """

    def __init__(self) -> None:
        """Inicializa os dicionários e o contador de IDs."""
        self._groups: dict[str, Group] = {}
        self._expenses: dict[str, Expense] = {}
        self._payments: dict[str, Payment] = {}
        self._seq = 0

    def _next_id(self) -> str:
        """Gera um ID sequencial simples."""
        self._seq += 1
        return str(self._seq)

    def add_group(self, group: Group) -> Group:
        """Persiste um novo grupo."""
        if not getattr(group, "id", None):
            group.id = self._next_id()
        self._groups[group.id] = group
        return group

    def get_group(self, group_id: str | int) -> Group:
        """Retorna um grupo ou levanta GroupNotFoundError."""
        group = self._groups.get(str(group_id))
        if group is None:
            raise GroupNotFoundError(f"Grupo {group_id} não encontrado")
        return group

    def get(self, group_id: str | int) -> Group:
        """Alias de get_group."""
        return self.get_group(group_id)

    def list_groups(self) -> list[Group]:
        """Lista todos os grupos."""
        return list(self._groups.values())

    def add_participant(self, group_id: str | int, participant: Participant) -> Participant:
        """Adiciona um participante ao grupo."""
        group = self.get_group(group_id)
        if not hasattr(group, "participants") or group.participants is None:
            group.participants = []
        group.participants.append(participant)
        return participant

    def add_expense(self, expense: Expense) -> Expense:
        """Persiste uma despesa e a associa ao grupo."""
        if not getattr(expense, "id", None):
            expense.id = self._next_id()
        self._expenses[expense.id] = expense
        group = self._groups.get(str(expense.group_id))
        if group is not None:
            if not hasattr(group, "expenses") or group.expenses is None:
                group.expenses = []
            group.expenses.append(expense)
        return expense

    def get_expense(self, expense_id: str) -> Expense:
        """Retorna uma despesa pelo id."""
        return self._expenses[str(expense_id)]

    def list_expenses(self, group_id: str | int | None = None) -> list[Expense]:
        """Lista despesas, opcionalmente filtrando por grupo."""
        if group_id is None:
            return list(self._expenses.values())
        return [e for e in self._expenses.values() if str(e.group_id) == str(group_id)]

    def add_payment(self, payment: Payment) -> Payment:
        """Persiste um pagamento e o associa ao grupo."""
        if not getattr(payment, "id", None):
            payment.id = self._next_id()
        self._payments[payment.id] = payment
        group = self._groups.get(str(payment.group_id))
        if group is not None:
            if not hasattr(group, "payments") or group.payments is None:
                group.payments = []
            group.payments.append(payment)
        return payment

    def list_payments(self, group_id: str | int | None = None) -> list[Payment]:
        """Lista pagamentos, opcionalmente filtrando por grupo."""
        if group_id is None:
            return list(self._payments.values())
        return [p for p in self._payments.values() if str(p.group_id) == str(group_id)]