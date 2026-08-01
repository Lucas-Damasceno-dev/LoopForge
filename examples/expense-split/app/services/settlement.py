"""Algoritmo de liquidação com número mínimo de transferências."""
from decimal import Decimal
from typing import Optional

from app.core.exceptions import SettlementError
from app.services.balances import calculate_balances, validate_balances
from app.utils import round_money

class SettlementTransfer(dict):
    """Representa uma transferência do plano de liquidação.

    Também funciona como dict para comparação direta em testes.
    """

    def __init__(self, payer: str, receiver: str, amount: Decimal, reason: str) -> None:
        """Inicializa a transferência.

        Args:
            payer: participante que paga.
            receiver: participante que recebe.
            amount: valor da transferência.
            reason: motivo da transferência.
        """
        super().__init__(
            payer=payer,
            receiver=receiver,
            amount=amount,
            reason=reason,
        )
        self.payer = payer
        self.receiver = receiver
        self.amount = amount
        self.reason = reason

Transfer = SettlementTransfer

def generate_settlement_plan(balances) -> list[SettlementTransfer]:
    """Gera um plano de liquidação usando greedy por maior saldo.

    Args:
        balances: mapeamento de participante para saldo líquido.

    Returns:
        list[SettlementTransfer]: transferências necessárias para zerar saldos.

    Raises:
        BalanceMismatchError: se os saldos forem inconsistentes.
    """
    validate_balances(balances)

    normalized = {str(key): round_money(value) for key, value in balances.items()}

    debtors = sorted(
        [[key, -value] for key, value in normalized.items() if value < -Decimal("0.005")],
        key=lambda item: (-item[1], item[0]),
    )
    creditors = sorted(
        [[key, value] for key, value in normalized.items() if value > Decimal("0.005")],
        key=lambda item: (-item[1], item[0]),
    )

    plan: list[SettlementTransfer] = []
    i = 0
    j = 0

    while i < len(debtors) and j < len(creditors):
        payer, debt = debtors[i]
        receiver, credit = creditors[j]
        amount = min(debt, credit)

        plan.append(
            SettlementTransfer(
                payer=payer,
                receiver=receiver,
                amount=round_money(amount),
                reason="Liquidação de despesas do grupo",
            )
        )

        debtors[i][1] = round_money(debtors[i][1] - amount)
        creditors[j][1] = round_money(creditors[j][1] - amount)

        if debtors[i][1] <= Decimal("0.005"):
            i += 1
        if creditors[j][1] <= Decimal("0.005"):
            j += 1

    return plan

class SettlementService:
    """Serviço para gerar planos de liquidação."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com repositório opcional."""
        self.repository = repository

    def generate_plan(self, balances) -> list[SettlementTransfer]:
        """Gera um plano de liquidação a partir de saldos.

        Args:
            balances: saldos por participante.

        Returns:
            list[SettlementTransfer]: lista de transferências.
        """
        return generate_settlement_plan(balances)

    def generate_plan_for_group(self, group_id) -> list[SettlementTransfer]:
        """Gera um plano de liquidação para todas as despesas de um grupo.

        Args:
            group_id: identificador do grupo.

        Returns:
            list[SettlementTransfer]: lista de transferências.

        Raises:
            SettlementError: se não houver repositório configurado.
        """
        if self.repository is None:
            raise SettlementError("Repository is required")
        expenses = self.repository.list_expenses(group_id)
        balances = calculate_balances(expenses)
        return generate_settlement_plan(balances)