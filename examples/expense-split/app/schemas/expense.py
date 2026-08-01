"""Schemas de despesas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class SplitRead(BaseModel):
    """Resposta de divisão de despesa."""

    model_config = ConfigDict(from_attributes=True)

    participant_id: UUID
    amount: Decimal
    percentage: Decimal | None = None

class ExpenseRead(BaseModel):
    """Resposta de despesa."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    group_id: UUID
    description: str
    paid_by: UUID
    amount: Decimal
    split_type: str
    splits: list[SplitRead] = []

class SplitIn(BaseModel):
    """Entrada de divisão customizada."""

    participant_id: UUID
    amount: Decimal | None = None
    percentage: Decimal | None = None

class EqualExpenseCreate(BaseModel):
    """Payload para despesa igualitária."""

    group_id: UUID
    description: str = Field(min_length=1)
    paid_by: UUID
    amount: Decimal = Field(gt=0)
    participant_ids: list[UUID] | None = None

class CustomExpenseCreate(BaseModel):
    """Payload para despesa customizada."""

    group_id: UUID
    description: str = Field(min_length=1)
    paid_by: UUID
    amount: Decimal = Field(gt=0)
    splits: list[SplitIn] = Field(min_length=1)