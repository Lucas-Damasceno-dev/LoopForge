from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Professional(Base):
    __tablename__ = "professionals"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    speciality: Mapped[str] = mapped_column(String(100), nullable=False)
    working_days: Mapped[str] = mapped_column(String(50), nullable=False, default="1,2,3,4,5")
    start_hour: Mapped[str] = mapped_column(String(5), nullable=False, default="08:00")
    end_hour: Mapped[str] = mapped_column(String(5), nullable=False, default="18:00")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="professional_profile")

    @property
    def id(self) -> int:
        return self.user_id

    @id.setter
    def id(self, value: int) -> None:
        self.user_id = value