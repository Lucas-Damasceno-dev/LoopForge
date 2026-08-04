from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_admin, get_current_professional
from app.db.session import get_db
from app.models import Service, User
from app.schemas.service import ServiceCreate, ServiceRead, ServiceUpdate

router = APIRouter()

@router.get("/", response_model=list[ServiceRead])
def list_services(
    professional_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List services, optionally filtered by professional_id.
    """
    query = db.query(Service)
    if professional_id:
        query = query.filter(Service.professional_id == professional_id)
    return query.all()

@router.post("/", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
def create_service(
    service_data: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a service. Only the professional (owner) or admin can create.
    """
    # Verify access: professional can create own services, admin can create any
    if current_user.role == "professional":
        if current_user.id != service_data.professional_id:
            raise HTTPException(status_code=403, detail="Cannot create service for another professional")
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Ensure professional exists (user with role professional)
    prof = db.query(User).filter(User.id == service_data.professional_id).first()
    if not prof or prof.role != "professional":
        raise HTTPException(status_code=400, detail="Invalid professional_id")

    service = Service(**service_data.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service

@router.get("/{service_id}", response_model=ServiceRead)
def get_service(service_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get a service by ID.
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service

@router.put("/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: int,
    service_data: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a service. Only the owning professional or admin can update.
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if current_user.role == "professional" and current_user.id != service.professional_id:
        raise HTTPException(status_code=403, detail="Cannot modify service of another professional")
    elif current_user.role != "admin" and current_user.role != "professional":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    for field, value in service_data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    db.commit()
    db.refresh(service)
    return service

@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Delete a service. Only the owning professional or admin can delete.
    """
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    if current_user.role == "professional" and current_user.id != service.professional_id:
        raise HTTPException(status_code=403, detail="Cannot delete service of another professional")
    elif current_user.role != "admin" and current_user.role != "professional":
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    db.delete(service)
    db.commit()
    return None