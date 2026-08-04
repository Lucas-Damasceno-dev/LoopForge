from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.service import ServiceRead
from app.schemas.user import UserRead


class AppointmentCreate(BaseModel):
    professional_id: int
    service_id: int
    start_time: datetime


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    professional_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    status: str
    cancel_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    service: ServiceRead | None = None
    client: UserRead | None = None
    professional: UserRead | None = None


class AppointmentCancel(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)