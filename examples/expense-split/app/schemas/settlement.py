"""Schemas de liquidação."""

from decimal import Decimal

from pydantic import BaseModel

class TransferRead(BaseModel):
    """Resposta de transferência sugerida."""

    from_participant: str
    to_participant: str
    amount: Decimal
    reason: str