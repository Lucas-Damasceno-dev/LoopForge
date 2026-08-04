"""Rotas de agendamentos."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Appointment, User
from app.schemas import AppointmentCancel, AppointmentCreate, AppointmentOut
from app.services.booking import BookingError, cancel_appointment, create_appointment

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    professional_id: int | None = None,
    status: str | None = None,
    past: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Appointment]:
    """Lista agendamentos conforme o papel do usuário logado."""
    query = db.query(Appointment)

    if user.role == "client":
        query = query.filter(Appointment.client_id == user.id)
    elif user.role == "professional":
        query = query.filter(Appointment.professional_id == user.id)

    if professional_id is not None:
        if user.role == "admin" or (user.role == "professional" and user.id == professional_id):
            query = query.filter(Appointment.professional_id == professional_id)
        else:
            raise HTTPException(status_code=403, detail="Não autorizado.")

    if status:
        query = query.filter(Appointment.status == status)

    if past:
        query = query.filter(Appointment.start_time < datetime.now())
    else:
        query = query.filter(Appointment.start_time >= datetime.now())

    return query.order_by(Appointment.start_time).all()


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    """Cria um agendamento aplicando as regras de conflito e expediente."""
    if user.role not in ("client", "admin"):
        raise HTTPException(status_code=403, detail="Apenas clientes ou admin podem criar agendamentos.")

    client_id = user.id
    if user.role == "admin" and payload.client_id is not None:
        client_id = payload.client_id

    try:
        appointment = create_appointment(
            db,
            client_id=client_id,
            professional_id=payload.professional_id,
            service_id=payload.service_id,
            start_time=payload.start_time,
        )
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return appointment


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentCancel,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Appointment:
    """Cancela um agendamento futuro com registro de motivo."""
    try:
        appointment = cancel_appointment(
            db,
            appointment_id=appointment_id,
            user=user,
            cancel_reason=payload.cancel_reason,
        )
    except BookingError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return appointment