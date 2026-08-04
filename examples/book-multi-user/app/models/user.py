from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False, default="client")  # client, professional, admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    professional_profile = relationship("Professional", back_populates="user", uselist=False)
    services = relationship("Service", back_populates="professional")
    client_appointments = relationship("Appointment", foreign_keys="Appointment.client_id", back_populates="client")
    professional_appointments = relationship("Appointment", foreign_keys="Appointment.professional_id", back_populates="professional")
    notifications = relationship("Notification", back_populates="user")