"""Serviços de dashboard do grupo."""
from collections.abc import Mapping
from decimal import Decimal
from types import SimpleNamespace

from app.services.balances import calculate_balances
from app.utils import first_not_none, round_money, sum_money

def _expense_amount(expense) -> Decimal:
    """Extrai o valor de uma despesa para o dashboard."""
    if isinstance(expense, Mapping):
        value = first_not_none(
            expense.get("total_amount"),
            expense.get("amount"),
            expense.get("total"),
            expense.get("value"),
        )
    else:
        value = first_not_none(
            getattr(expense, "total_amount", None),
            getattr(expense, "amount", None),
            getattr(expense, "total", None),
            getattr(expense, "value", None),
        )

    if value is None:
        return Decimal("0.00")
    return round_money(value)

def build_dashboard(group=None, expenses=None) -> dict:
    """Constrói o dashboard de um grupo.

    Args:
        group: objeto do grupo.
        expenses: lista opcional de despesas; se None, usa ``group.expenses``.

    Returns:
        dict: contém nome, participantes, saldos e total de despesas.
    """
    if isinstance(group, (list, tuple)):
        expenses = group
        group = SimpleNamespace(name="Group", participants=[])

    if expenses is None:
        expenses = getattr(group, "expenses", [])

    balances = calculate_balances(expenses)
    total_expenses = sum_money(_expense_amount(expense) for expense in expenses)

    return {
        "name": getattr(group, "name", None),
        "participants": list(getattr(group, "participants", [])),
        "balances": balances,
        "total_expenses": total_expenses,
    }

class DashboardService:
    """Serviço de dashboards."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com repositório opcional."""
        self.repository = repository

    def build(self, group, expenses=None) -> dict:
        """Constrói o dashboard do grupo."""
        return build_dashboard(group, expenses)

    def get_dashboard(self, group, expenses=None) -> dict:
        """Alias para ``build``."""
        return build_dashboard(group, expenses)