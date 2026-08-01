"""Schemas de grupos e participantes."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class ParticipantRead(BaseModel):
    """Resposta de participante."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr | None = None
    status: str
    balance: Decimal = Decimal("0.00")

class GroupCreate(BaseModel):
    """Payload para criação de grupo."""

    name: str = Field(min_length=1, max_length=120)
    participant_emails: list[EmailStr] = []

class GroupRead(BaseModel):
    """Resposta de grupo."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    participants: list[ParticipantRead] = []

class ParticipantCreate(BaseModel):
    """Payload para adicionar participante."""

    email: EmailStr