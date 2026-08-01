"""Cálculo de saldos individuais."""

from collections import defaultdict
from decimal import Decimal

from app.core.exceptions import InconsistentBalanceError

def calculate_balances(expenses) -> dict[str, Decimal]:
    """Calcula saldos líquidos a partir das despesas de um grupo."""
    balances: dict[str, Decimal] = defaultdict(Decimal)

    for expense in expenses:
        amount = Decimal(str(expense.amount))
        payer = str(expense.paid_by)
        balances[payer] += amount

        for split in expense.splits:
            participant = str(split.participant_id)
            split_amount = Decimal(str(split.amount))
            balances[participant] -= split_amount

    balances = {key: value for key, value in balances.items() if value != 0}

    total = sum(balances.values(), Decimal("0.00"))
    if total != 0:
        raise InconsistentBalanceError(
            f"A soma dos saldos é {total}; deveria ser zero."
        )

    return balances