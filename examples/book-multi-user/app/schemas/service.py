from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    professional_id: int | None = None
    name: str = Field(..., min_length=1, max_length=100)
    duration_minutes: int = Field(..., gt=0, le=1440)
    price: Decimal = Field(..., ge=0, max_digits=10, decimal_places=2)


class ServiceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    duration_minutes: int | None = Field(default=None, gt=0, le=1440)
    price: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class ServiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    professional_id: int
    name: str
    duration_minutes: int
    price: Decimal