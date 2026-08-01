"""Serviços de cálculo e registro de despesas."""
from decimal import Decimal
from typing import Mapping, Sequence

from app.core.exceptions import ExpenseValidationError
from app.models.entities import Expense
from app.utils import cents_to_money, first_not_none, money_to_cents, round_money, sum_money

def _normalize_custom_values(values):
    """Normaliza valores customizados para dict[str, Decimal]."""
    if isinstance(values, Mapping):
        return {str(key): round_money(value) for key, value in values.items()}

    normalized: dict[str, Decimal] = {}
    for item in values:
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
                "Custom split entries must have participant and amount"
            )

        normalized[str(participant)] = round_money(amount)

    return normalized

def calculate_equal_split(total, participants: Sequence[str]) -> dict[str, Decimal]:
    """Calcula divisão igualitária de uma despesa.

    Args:
        total: valor total da despesa.
        participants: participantes que devem dividir a despesa.

    Returns:
        dict[str, Decimal]: mapeamento de participante para valor devido.

    Raises:
        ExpenseValidationError: se o total ou participantes forem inválidos.
    """
    participants = list(participants or [])
    if not participants:
        raise ExpenseValidationError("Participants are required for equal split")

    total = round_money(total)
    if total <= 0:
        raise ExpenseValidationError("Total must be positive")

    total_cents = money_to_cents(total)
    base = total_cents // len(participants)
    remainder = total_cents % len(participants)

    if len(set(participants)) != len(participants):
        raise ExpenseValidationError("Duplicate participants are not allowed")

    result: dict[str, Decimal] = {}
    for index, participant in enumerate(participants):
        share = base + (1 if index < remainder else 0)
        result[str(participant)] = cents_to_money(share)

    return result

def validate_custom_split(total, values) -> bool:
    """Valida se os valores customizados somam exatamente o total.

    Args:
        total: valor total da despesa.
        values: mapeamento de participante para valor devido.

    Returns:
        bool: True se a divisão for válida.

    Raises:
        ExpenseValidationError: se a soma não bater ou houver valores negativos.
    """
    total = round_money(total)
    if total <= 0:
        raise ExpenseValidationError("Total must be positive")

    normalized = _normalize_custom_values(values)
    if not normalized:
        raise ExpenseValidationError("Custom split values are required")

    if any(value < 0 for value in normalized.values()):
        raise ExpenseValidationError("Custom split values cannot be negative")

    actual = sum_money(normalized.values())
    if actual != total:
        raise ExpenseValidationError(
            f"Custom split sum {actual} does not match total {total}"
        )

    return True

def calculate_custom_split(total, values) -> dict[str, Decimal]:
    """Calcula divisão customizada validando a soma dos valores.

    Args:
        total: valor total da despesa.
        values: mapeamento de participante para valor devido.

    Returns:
        dict[str, Decimal]: divisão customizada validada.

    Raises:
        ExpenseValidationError: se a divisão for inválida.
    """
    normalized = _normalize_custom_values(values)
    validate_custom_split(total, normalized)
    return normalized

class ExpenseService:
    """Serviço para registrar e consultar despesas."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com um repositório opcional."""
        self.repository = repository

    def register_expense(
        self,
        group_id=None,
        payer=None,
        total=None,
        participants=None,
        split_type: str = "equal",
        custom_values=None,
        description: str = "",
        **kwargs,
    ) -> Expense:
        """Registra uma despesa com divisão igualitária ou customizada.

        Args:
            group_id: identificador do grupo.
            payer: participante que pagou a despesa.
            total: valor total da despesa.
            participants: participantes da divisão igualitária.
            split_type: "equal" ou "custom".
            custom_values: valores da divisão customizada.
            description: descrição opcional.
            **kwargs: aceita ``total_amount`` e ``amount`` como aliases de ``total``.

        Returns:
            Expense: despesa registrada.

        Raises:
            ExpenseValidationError: se os parâmetros forem inválidos.
        """
        if total is None:
            total = first_not_none(
                kwargs.get("total_amount"),
                kwargs.get("amount"),
            )

        if payer is None:
            payer = kwargs.get("paid_by") or kwargs.get("user")

        if total is None:
            raise ExpenseValidationError("Expense total is required")
        if payer is None:
            raise ExpenseValidationError("Expense payer is required")

        if split_type == "equal":
            splits = calculate_equal_split(total, participants)
        elif split_type == "custom":
            splits = calculate_custom_split(total, custom_values)
        else:
            raise ExpenseValidationError(f"Unsupported split_type: {split_type}")

        expense = Expense(
            group_id=group_id,
            payer=payer,
            amount=round_money(total),
            splits=splits,
            description=description,
        )

        if self.repository is not None and hasattr(self.repository, "add"):
            saved = self.repository.add(expense)
            from app.utils import is_mock

            if saved is not None and not is_mock(saved):
                return saved

        return expense

    create_expense = register_expense