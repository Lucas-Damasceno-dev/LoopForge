from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Service, Appointment, Professional, Notification
from app.schemas.appointment import AppointmentCreate, AppointmentRead, AppointmentCancel

router = APIRouter()

def get_professional_working_hours(db: Session, professional_user_id: int) -> tuple[str, str, str]:
    """
    Get working hours and days for a professional user.
    If no Professional record, use defaults.
    """
    professional = db.query(Professional).filter(Professional.user_id == professional_user_id).first()
    if professional:
        return professional.working_days, professional.start_hour, professional.end_hour
    return "0,1,2,3,4", "08:00", "18:00"

def is_within_working_hours(start: datetime, end: datetime, working_days: str, start_hour: str, end_hour: str) -> bool:
    """
    Check if the slot is within working hours and days.
    """
    # Day of week: 0=Mon? Python: Monday=0, Sunday=6
    # Our working_days string: 0=Dom, 6=Sáb (as per spec)
    # Convert: spec: 0=Dom, 6=Sáb -> Python: Monday=0, Sunday=6
    # So mapping: 0->6 (Sunday), 1->0 (Monday), 2->1,...,6->5 (Saturday)
    day_map = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}
    allowed_days = set(int(d) for d in working_days.split(",") if d.strip())
    python_day = start.weekday()  # Monday=0
    day_index = next((k for k, v in day_map.items() if v == python_day), None)
    if day_index is None or day_index not in allowed_days:
        return False

    # Check hours
    start_hm = start.strftime("%H:%M")
    end_hm = end.strftime("%H:%M")
    if start_hour <= start_hm and end_hm <= end_hour:
        return True
    return False

def check_conflict(db: Session, professional_id: int, start: datetime, end: datetime) -> bool:
    """
    Check if there is an overlapping confirmed appointment for the professional.
    """
    overlapping = db.query(Appointment).filter(
        Appointment.professional_id == professional_id,
        Appointment.status == "confirmed",
        Appointment.start_time < end,
        Appointment.end_time > start
    ).first()
    return overlapping is not None

@router.get("/", response_model=list[AppointmentRead])
def list_appointments(
    as_professional: bool = False,
    as_client: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List appointments. Behavior:
    - admin: all
    - professional: own appointments if as_professional=true
    - client: own appointments if as_client=true (default)
    """
    query = db.query(Appointment)
    if current_user.role == "admin":
        # Admin sees all; filters can be applied if provided
        pass
    elif current_user.role == "professional":
        if as_professional:
            query = query.filter(Appointment.professional_id == current_user.id)
        else:
            raise HTTPException(status_code=403, detail="Professional must use ?as_professional=true")
    elif current_user.role == "client":
        if as_client:
            query = query.filter(Appointment.client_id == current_user.id)
        else:
            # default to client's own
            query = query.filter(Appointment.client_id == current_user.id)
    else:
        raise HTTPException(status_code=403, detail="Invalid role")

    return query.order_by(Appointment.start_time).all()

@router.post("/", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create an appointment with business rules validation.
    """
    # Only clients can create appointments
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can create appointments")

    # Validate service exists and belongs to professional
    service = db.query(Service).filter(Service.id == appointment_data.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if service.professional_id != appointment_data.professional_id:
        raise HTTPException(status_code=400, detail="Service does not belong to this professional")

    # Compute end_time based on duration
    start = appointment_data.start_time
    end = start + timedelta(minutes=service.duration_minutes)

    # Rule: cannot be in the past
    if start < datetime.now():
        raise HTTPException(status_code=400, detail="Cannot book in the past")

    # Rule: within working hours
    working_days, start_hour, end_hour = get_professional_working_hours(db, appointment_data.professional_id)
    if not is_within_working_hours(start, end, working_days, start_hour, end_hour):
        raise HTTPException(status_code=400, detail="Appointment outside working hours")

    # Rule: no conflict
    if check_conflict(db, appointment_data.professional_id, start, end):
        raise HTTPException(status_code=409, detail="Time slot conflict")

    # Create appointment
    appointment = Appointment(
        client_id=current_user.id,
        professional_id=appointment_data.professional_id,
        service_id=appointment_data.service_id,
        start_time=start,
        end_time=end,
        status="confirmed"
    )
    db.add(appointment)
    db.flush()  # get ID

    # Create notifications for client and professional
    for user_id in [current_user.id, appointment_data.professional_id]:
        notif = Notification(
            user_id=user_id,
            message=f"Novo agendamento: {service.name} em {start.strftime('%d/%m/%Y %H:%M')}"
        )
        db.add(notif)
    db.commit()
    db.refresh(appointment)
    return appointment

@router.post("/{appointment_id}/cancel", response_model=AppointmentRead)
def cancel_appointment(
    appointment_id: int,
    cancel_data: AppointmentCancel,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel an appointment. Client or admin can cancel.
    Cannot cancel past appointments.
    """
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Permission: client who booked or admin
    if current_user.role not in ["admin"] and (current_user.id != appointment.client_id):
        raise HTTPException(status_code=403, detail="Only the client who booked or admin can cancel")

    # Rule: cannot cancel past appointments
    if appointment.start_time < datetime.now():
        raise HTTPException(status_code=400, detail="Cannot cancel a past appointment")

    # Update status
    appointment.status = "cancelled"
    appointment.cancel_reason = cancel_data.reason
    db.commit()
    db.refresh(appointment)

    # Notification for both parties
    for user_id in [appointment.client_id, appointment.professional_id]:
        notif = Notification(
            user_id=user_id,
            message=f"Agendamento cancelado: {appointment.service.name} em {appointment.start_time.strftime('%d/%m/%Y %H:%M')}"
        )
        db.add(notif)
    db.commit()
    return appointment