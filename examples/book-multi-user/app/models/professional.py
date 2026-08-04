from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base

class Professional(Base):
    __tablename__ = "professionals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    speciality = Column(String(100), nullable=False, default="")
    working_days = Column(String(50), nullable=False, default="0,1,2,3,4")  # 0=Dom, 6=Sáb
    start_hour = Column(String(5), nullable=False, default="08:00")  # 24h format
    end_hour = Column(String(5), nullable=False, default="18:00")

    user = relationship("User", back_populates="professional_profile")