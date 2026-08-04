from pydantic import BaseModel, Field
from datetime import datetime

class AppointmentBase(BaseModel):
    client_id: int
    professional_id: int
    service_id: int
    start_time: datetime
    end_time: datetime

class AppointmentCreate(BaseModel):
    professional_id: int
    service_id: int
    start_time: datetime

class AppointmentRead(AppointmentBase):
    id: int
    status: str
    cancel_reason: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True

class AppointmentCancel(BaseModel):
    reason: str = Field(..., min_length=1, max_length=255)