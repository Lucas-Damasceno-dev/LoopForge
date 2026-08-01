"""Cálculo e validação de saldos individuais e do grupo."""
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.core.exceptions import BalanceMismatchError, ExpenseValidationError
from app.services.expense import calculate_equal_split
from app.utils import first_not_none, round_money, sum_money

def _as_decimal(value) -> Decimal:
    """Converte um valor para Decimal."""
    return Decimal(str(value))

def _expense_total(expense) -> Decimal:
    """Extrai o valor total de uma despesa."""
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
        raise ExpenseValidationError("Expense total amount is missing")

    return _as_decimal(value)

def _expense_payer(expense) -> str:
    """Extrai o pagador de uma despesa."""
    if isinstance(expense, Mapping):
        value = first_not_none(
            expense.get("payer"),
            expense.get("paid_by"),
            expense.get("user"),
        )
    else:
        value = first_not_none(
            getattr(expense, "payer", None),
            getattr(expense, "paid_by", None),
            getattr(expense, "user", None),
        )

    if value is None:
        raise ExpenseValidationError("Expense payer is missing")

    return str(value)

def _expense_splits(expense) -> dict[str, Decimal]:
    """Extrai a divisão de uma despesa."""
    if isinstance(expense, Mapping):
        raw = first_not_none(
            expense.get("splits"),
            expense.get("split"),
            expense.get("division"),
        )
    else:
        raw = first_not_none(
            getattr(expense, "splits", None),
            getattr(expense, "split", None),
            getattr(expense, "division", None),
        )

    if raw is None:
        if isinstance(expense, Mapping):
            participants = expense.get("participants")
        else:
            participants = getattr(expense, "participants", None)

        if participants:
            return calculate_equal_split(_expense_total(expense), participants)

        raise ExpenseValidationError("Expense splits are missing")

    if isinstance(raw, Mapping):
        return {str(key): _as_decimal(value) for key, value in raw.items()}

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        result: dict[str, Decimal] = {}
        for item in raw:
            if isinstance(item, Mapping):
                participant = first_not_none(
                    item.get("participant"),
                    item.get("email"),
                    item.get("user"),
                )
                amount = first_not_none(item.get("amount"), item.get("share"))
            else:
                participant = first_not_none(
                    getattr(item, "participant", None),
                    getattr(item, "email", None),
                    getattr(item, "user", None),
                )
                amount = first_not_none(
                    getattr(item, "amount", None),
                    getattr(item, "share", None),
                )

            if participant is None or amount is None:
                raise ExpenseValidationError(
                    "Expense split entries must have participant and amount"
                )

            result[str(participant)] = _as_decimal(amount)

        return result

    raise ExpenseValidationError("Expense splits have invalid format")

def calculate_balances(expenses) -> dict[str, Decimal]:
    """Calcula o saldo líquido de cada participante.

    Args:
        expenses: lista de despesas a considerar.

    Returns:
        dict[str, Decimal]: saldo por participante.
    """
    balances: dict[str, Decimal] = {}

    for expense in expenses:
        total = _expense_total(expense)
        payer = _expense_payer(expense)
        splits = _expense_splits(expense)

        balances[payer] = round_money(balances.get(payer, Decimal("0.00")) + total)

        for participant, share in splits.items():
            balances[participant] = round_money(
                balances.get(participant, Decimal("0.00")) - share
            )

    return balances

def validate_balances(balances) -> bool:
    """Valida a consistência dos saldos.

    Args:
        balances: dict de participante para saldo.

    Returns:
        bool: True se os saldos forem consistentes.

    Raises:
        BalanceMismatchError: se a soma dos saldos não for zero ou se créditos
            e débitos não forem iguais.
    """
    if not balances:
        return True

    normalized = {str(key): _as_decimal(value) for key, value in balances.items()}
    total = sum_money(normalized.values())

    if abs(total) > Decimal("0.01"):
        raise BalanceMismatchError(f"Balances do not sum to zero: {total}")

    credits = sum_money(value for value in normalized.values() if value > 0)
    debits = sum_money(-value for value in normalized.values() if value < 0)

    if abs(credits - debits) > Decimal("0.01"):
        raise BalanceMismatchError(
            f"Credits {credits} do not match debits {debits}"
        )

    return True

class BalanceService:
    """Serviço de cálculo e validação de saldos."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com repositório opcional."""
        self.repository = repository

    def calculate(self, expenses) -> dict[str, Decimal]:
        """Calcula saldos a partir de despesas."""
        return calculate_balances(expenses)

    def validate(self, balances) -> bool:
        """Valida se os saldos são consistentes."""
        return validate_balances(balances)

    def for_group(self, group_id) -> dict[str, Decimal]:
        """Calcula saldos de todas as despesas de um grupo."""
        if self.repository is None:
            raise ExpenseValidationError("Repository is required")
        expenses = self.repository.list_expenses(group_id)
        return calculate_balances(expenses)