from pydantic import BaseModel, Field
from datetime import datetime

class ServiceBase(BaseModel):
    professional_id: int
    name: str = Field(..., min_length=1, max_length=100)
    duration_minutes: int = Field(..., gt=0, le=600)
    price: float = Field(..., ge=0)

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    name: str | None = None
    duration_minutes: int | None = Field(None, gt=0, le=600)
    price: float | None = Field(None, ge=0)

class ServiceRead(ServiceBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True