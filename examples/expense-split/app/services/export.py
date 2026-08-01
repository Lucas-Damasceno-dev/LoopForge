"""Exportação de despesas em CSV."""
import csv
import io
from collections.abc import Mapping

from app.utils import first_not_none

def _expense_value(expense, *names):
    """Obtém o primeiro campo existente em uma despesa."""
    if isinstance(expense, Mapping):
        return first_not_none(*(expense.get(name) for name in names))
    return first_not_none(*(getattr(expense, name, None) for name in names))

def export_expenses_csv(expenses) -> str:
    """Gera um CSV com as despesas informadas.

    Args:
        expenses: lista de despesas.

    Returns:
        str: conteúdo CSV.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "group_id", "payer", "amount", "description", "created_at"]
    )

    for expense in expenses:
        writer.writerow(
            [
                _expense_value(expense, "id", "expense_id") or "",
                _expense_value(expense, "group_id") or "",
                _expense_value(expense, "payer", "paid_by", "user") or "",
                _expense_value(expense, "amount", "total_amount", "total") or "",
                _expense_value(expense, "description") or "",
                _expense_value(expense, "created_at") or "",
            ]
        )

    return output.getvalue()

class ExportService:
    """Serviço de exportação de despesas."""

    def __init__(self, repository=None) -> None:
        """Inicializa o serviço com repositório opcional."""
        self.repository = repository

    def export_expenses(self, expenses) -> str:
        """Exporta uma lista de despesas para CSV."""
        return export_expenses_csv(expenses)

    def export_group(self, group_id) -> str:
        """Exporta todas as despesas de um grupo para CSV."""
        if self.repository is None:
            return export_expenses_csv([])
        expenses = self.repository.list_expenses(group_id)
        return export_expenses_csv(expenses)