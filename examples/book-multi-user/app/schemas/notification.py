from pydantic import BaseModel
from datetime import datetime

class NotificationRead(BaseModel):
    id: int
    user_id: int
    message: str
    read: bool
    created_at: datetime

    class Config:
        from_attributes = True