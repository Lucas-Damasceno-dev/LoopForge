"""Rotas de profissionais."""
from __future__ import annotations

from datetime import time

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_admin, require_professional
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models import Appointment, Notification, Professional, Service, User
from app.schemas import (
    AvailabilityUpdate,
    ProfessionalCreate,
    ProfessionalOut,
    ProfessionalUpdate,
)
from app.services.availability import parse_working_days

router = APIRouter(prefix="/professionals", tags=["professionals"])


def _validate_schedule(working_days: str, start_hour: str, end_hour: str) -> None:
    """Valida dias de trabalho e horários de expediente."""
    try:
        parse_working_days(working_days)
        start = time.fromisoformat(start_hour)
        end = time.fromisoformat(end_hour)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="working_days, start_hour ou end_hour inválidos.") from exc

    if start >= end:
        raise HTTPException(status_code=422, detail="start_hour deve ser anterior a end_hour.")


def _delete_user_cascade(db: Session, user_id: int) -> None:
    """Remove registros associados ao usuário antes de excluí-lo."""
    db.query(Notification).filter(Notification.user_id == user_id).delete(synchronize_session=False)
    db.query(Appointment).filter(
        or_(Appointment.client_id == user_id, Appointment.professional_id == user_id)
    ).delete(synchronize_session=False)
    db.query(Service).filter(Service.professional_id == user_id).delete(synchronize_session=False)
    db.query(Professional).filter(Professional.id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)


@router.get("", response_model=list[ProfessionalOut])
def list_professionals(db: Session = Depends(get_db)) -> list[Professional]:
    """Lista todos os profissionais cadastrados."""
    return db.query(Professional).join(User).order_by(User.name).all()


@router.get("/{professional_id}", response_model=ProfessionalOut)
def get_professional(professional_id: int, db: Session = Depends(get_db)) -> Professional:
    """Retorna um profissional pelo id."""
    professional = db.get(Professional, professional_id)
    if professional is None:
        raise HTTPException(status_code=404, detail="Profissional não encontrado.")
    return professional


@router.post("", response_model=ProfessionalOut, status_code=201)
def create_professional(
    payload: ProfessionalCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Professional:
    """Cria um profissional (somente admin)."""
    _validate_schedule(payload.working_days, payload.start_hour, payload.end_hour)

    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=get_password_hash(payload.password),
        role="professional",
    )
    db.add(user)
    db.flush()

    professional = db.get(Professional, user.id)
    if professional is None:
        professional = Professional(id=user.id)
        db.add(professional)
        db.flush()

    professional.speciality = payload.speciality
    professional.working_days = payload.working_days
    professional.start_hour = payload.start_hour
    professional.end_hour = payload.end_hour

    db.commit()
    db.refresh(user)
    db.refresh(professional)
    return professional


@router.put("/me/availability", response_model=ProfessionalOut)
def update_my_availability(
    payload: AvailabilityUpdate,
    professional: Professional = Depends(require_professional),
    db: Session = Depends(get_db),
) -> Professional:
    """Profissional atualiza a própria jornada de trabalho."""
    _validate_schedule(payload.working_days, payload.start_hour, payload.end_hour)

    professional.working_days = payload.working_days
    professional.start_hour = payload.start_hour
    professional.end_hour = payload.end_hour

    db.commit()
    db.refresh(professional)
    return professional


@router.put("/{professional_id}", response_model=ProfessionalOut)
def update_professional(
    professional_id: int,
    payload: ProfessionalUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Professional:
    """Atualiza dados de um profissional (somente admin)."""
    professional = db.get(Professional, professional_id)
    if professional is None:
        raise HTTPException(status_code=404, detail="Profissional não encontrado.")

    new_working_days = payload.working_days or professional.working_days
    new_start_hour = payload.start_hour or professional.start_hour
    new_end_hour = payload.end_hour or professional.end_hour
    _validate_schedule(new_working_days, new_start_hour, new_end_hour)

    if payload.speciality is not None:
        professional.speciality = payload.speciality
    professional.working_days = new_working_days
    professional.start_hour = new_start_hour
    professional.end_hour = new_end_hour

    db.commit()
    db.refresh(professional)
    return professional


@router.delete("/{professional_id}", status_code=204)
def delete_professional(
    professional_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Exclui um profissional e seus dados associados (somente admin)."""
    professional = db.get(Professional, professional_id)
    if professional is None:
        raise HTTPException(status_code=404, detail="Profissional não encontrado.")

    _delete_user_cascade(db, professional_id)
    db.commit()
    return Response(status_code=204)