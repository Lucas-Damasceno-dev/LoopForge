"""Serviço central de agendamento e cancelamento."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Appointment, Notification, Professional, Service, User
from app.services.availability import is_working_time


class BookingError(Exception):
    """Erro de regra de negócio no agendamento.

    Attributes:
        message: Mensagem de erro.
        status_code: Código HTTP sugerido.
    """

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def create_appointment(
    db: Session,
    *,
    client_id: int,
    professional_id: int,
    service_id: int,
    start_time: datetime,
) -> Appointment:
    """Cria um agendamento respeitando todas as regras de domínio.

    Regras aplicadas:
    - serviço deve pertencer ao profissional;
    - horário não pode estar no passado;
    - horário deve estar dentro da jornada de trabalho;
    - não pode haver conflito com outro agendamento ativo.
    """
    if start_time.tzinfo is not None:
        start_time = start_time.replace(tzinfo=None)

    service = db.get(Service, service_id)
    if service is None:
        raise BookingError("Serviço não encontrado.", 404)
    if service.professional_id != professional_id:
        raise BookingError("Serviço não pertence ao profissional informado.", 400)

    professional = db.get(Professional, professional_id)
    if professional is None:
        raise BookingError("Profissional não encontrado.", 404)

    client = db.get(User, client_id)
    if client is None:
        raise BookingError("Cliente não encontrado.", 404)

    end_time = start_time + timedelta(minutes=service.duration_minutes)

    if start_time <= datetime.now():
        raise BookingError("Agendamento não pode ser no passado.", 400)

    if not is_working_time(professional, start_time, end_time):
        raise BookingError("Horário fora do expediente do profissional.", 400)

    overlapping = (
        db.query(Appointment)
        .filter(
            Appointment.professional_id == professional_id,
            Appointment.status != "canceled",
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        )
        .first()
    )
    if overlapping:
        raise BookingError("Conflito de horário com outro agendamento.", 409)

    appointment = Appointment(
        client_id=client_id,
        professional_id=professional_id,
        service_id=service_id,
        start_time=start_time,
        end_time=end_time,
        status="confirmed",
    )
    db.add(appointment)
    db.flush()

    professional_name = professional.user.name if professional.user else "Profissional"
    db.add(
        Notification(
            user_id=client_id,
            message=f"Seu agendamento de {service.name} com {professional_name} em {start_time} foi confirmado.",
            read=False,
        )
    )
    db.add(
        Notification(
            user_id=professional_id,
            message=f"Novo agendamento de {client.name} para {service.name} em {start_time}.",
            read=False,
        )
    )

    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, *, appointment_id: int, user: User, cancel_reason: str) -> Appointment:
    """Cancela um agendamento futuro, registrando motivo e notificações."""
    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise BookingError("Agendamento não encontrado.", 404)

    if user.role != "admin" and appointment.client_id != user.id:
        raise BookingError("Você não tem permissão para cancelar este agendamento.", 403)

    if appointment.start_time <= datetime.now():
        raise BookingError("Agendamentos passados não podem ser cancelados.", 400)

    appointment.status = "canceled"
    appointment.cancel_reason = cancel_reason
    db.flush()

    db.add(
        Notification(
            user_id=appointment.client_id,
            message=f"Seu agendamento de {appointment.service_name} foi cancelado. Motivo: {cancel_reason}",
            read=False,
        )
    )
    db.add(
        Notification(
            user_id=appointment.professional_id,
            message=(
                f"Agendamento cancelado por {'admin' if user.role == 'admin' else 'cliente'}. "
                f"Motivo: {cancel_reason}"
            ),
            read=False,
        )
    )

    db.commit()
    db.refresh(appointment)
    return appointment