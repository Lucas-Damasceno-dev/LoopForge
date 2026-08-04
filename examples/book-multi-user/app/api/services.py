"""Rotas de serviços."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Professional, Service, User
from app.schemas import ServiceCreate, ServiceOut, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


@router.get("", response_model=list[ServiceOut])
def list_services(
    professional_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[Service]:
    """Lista serviços, opcionalmente filtrando por profissional."""
    query = db.query(Service)
    if professional_id is not None:
        query = query.filter(Service.professional_id == professional_id)
    return query.order_by(Service.name).all()


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(service_id: int, db: Session = Depends(get_db)) -> Service:
    """Retorna um serviço pelo id."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")
    return service


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(
    payload: ServiceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Service:
    """Cria um serviço (profissional ou admin)."""
    if user.role == "admin":
        professional_id = payload.professional_id
        if professional_id is None:
            raise HTTPException(status_code=422, detail="professional_id é obrigatório para admin.")
    elif user.role == "professional":
        if payload.professional_id is not None and payload.professional_id != user.id:
            raise HTTPException(status_code=403, detail="Profissionais só podem criar serviços para si.")
        professional_id = user.id
    else:
        raise HTTPException(status_code=403, detail="Apenas profissionais ou admin podem criar serviços.")

    professional = db.get(Professional, professional_id)
    if professional is None:
        raise HTTPException(status_code=404, detail="Profissional não encontrado.")

    service = Service(
        professional_id=professional_id,
        name=payload.name,
        duration_minutes=payload.duration_minutes,
        price=payload.price,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.put("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Service:
    """Atualiza um serviço (dono profissional ou admin)."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")

    if user.role not in ("professional", "admin"):
        raise HTTPException(status_code=403, detail="Permissão insuficiente.")
    if user.role == "professional" and service.professional_id != user.id:
        raise HTTPException(status_code=403, detail="Você não é dono deste serviço.")

    if payload.name is not None:
        service.name = payload.name
    if payload.duration_minutes is not None:
        service.duration_minutes = payload.duration_minutes
    if payload.price is not None:
        service.price = payload.price

    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Remove um serviço (dono profissional ou admin)."""
    service = db.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Serviço não encontrado.")

    if user.role not in ("professional", "admin"):
        raise HTTPException(status_code=403, detail="Permissão insuficiente.")
    if user.role == "professional" and service.professional_id != user.id:
        raise HTTPException(status_code=403, detail="Você não é dono deste serviço.")

    db.delete(service)
    db.commit()
    return Response(status_code=204)