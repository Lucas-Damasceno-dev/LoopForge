from pydantic import BaseModel, Field
from datetime import datetime

class ProfessionalBase(BaseModel):
    user_id: int
    speciality: str = Field(default="", max_length=100)
    working_days: str = Field(default="0,1,2,3,4", description="Comma-separated days, 0=Dom, 6=Sáb")
    start_hour: str = Field(default="08:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")
    end_hour: str = Field(default="18:00", pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

class ProfessionalCreate(ProfessionalBase):
    pass

class ProfessionalUpdate(BaseModel):
    speciality: str | None = None
    working_days: str | None = None
    start_hour: str | None = None
    end_hour: str | None = None

class ProfessionalRead(ProfessionalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True