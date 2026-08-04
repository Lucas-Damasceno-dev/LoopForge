"""Seed inicial do banco de dados."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import Professional, Service, User


def seed_initial_data(db: Session) -> None:
    """Cria dados iniciais: admin, dois profissionais e quatro serviços."""
    if db.query(User).filter(User.email == "admin@example.com").first():
        return

    admin = User(
        name="Admin",
        email="admin@example.com",
        password_hash=get_password_hash("admin123"),
        role="admin",
    )
    db.add(admin)
    db.flush()

    ana = User(
        name="Ana",
        email="prof1@example.com",
        password_hash=get_password_hash("prof123"),
        role="professional",
    )
    db.add(ana)
    db.flush()

    bruno = User(
        name="Bruno",
        email="prof2@example.com",
        password_hash=get_password_hash("prof123"),
        role="professional",
    )
    db.add(bruno)
    db.flush()

    prof_ana = db.get(Professional, ana.id)
    if prof_ana is not None:
        prof_ana.speciality = "Cabeleireira"
        prof_ana.working_days = "1,2,3,4,5"
        prof_ana.start_hour = "08:00"
        prof_ana.end_hour = "18:00"

    prof_bruno = db.get(Professional, bruno.id)
    if prof_bruno is not None:
        prof_bruno.speciality = "Manicure"
        prof_bruno.working_days = "1,2,3,4,5"
        prof_bruno.start_hour = "08:00"
        prof_bruno.end_hour = "18:00"

    db.add_all(
        [
            Service(professional_id=ana.id, name="Corte de cabelo", duration_minutes=30, price=50.0),
            Service(professional_id=ana.id, name="Barba", duration_minutes=20, price=30.0),
            Service(professional_id=ana.id, name="Combo Corte + Barba", duration_minutes=50, price=70.0),
            Service(professional_id=bruno.id, name="Manicure", duration_minutes=45, price=40.0),
        ]
    )
    db.commit()