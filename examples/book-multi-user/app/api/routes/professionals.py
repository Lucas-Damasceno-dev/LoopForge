from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.models import User, Professional
from app.schemas.professional import ProfessionalCreate, ProfessionalRead, ProfessionalUpdate

router = APIRouter()

@router.get("/", response_model=list[ProfessionalRead])
def list_professionals(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    List all professionals (requires authentication).
    """
    professionals = db.query(Professional).all()
    return professionals

@router.post("/", response_model=ProfessionalRead, status_code=status.HTTP_201_CREATED)
def create_professional(
    professional_data: ProfessionalCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Create a professional (admin only).
    """
    # Check user exists and has role professional
    user = db.query(User).filter(User.id == professional_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.role != "professional":
        raise HTTPException(status_code=400, detail="User must have role 'professional'")

    # Check if professional already exists
    if db.query(Professional).filter(Professional.user_id == user.id).first():
        raise HTTPException(status_code=400, detail="Professional already exists for this user")

    professional = Professional(**professional_data.model_dump())
    db.add(professional)
    db.commit()
    db.refresh(professional)
    return professional

@router.get("/{professional_id}", response_model=ProfessionalRead)
def get_professional(professional_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Get a professional by ID.
    """
    professional = db.query(Professional).filter(Professional.id == professional_id).first()
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found")
    return professional

@router.put("/{professional_id}", response_model=ProfessionalRead)
def update_professional(
    professional_id: int,
    professional_data: ProfessionalUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Update a professional (admin only).
    """
    professional = db.query(Professional).filter(Professional.id == professional_id).first()
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found")

    for field, value in professional_data.model_dump(exclude_unset=True).items():
        setattr(professional, field, value)
    db.commit()
    db.refresh(professional)
    return professional

@router.delete("/{professional_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_professional(professional_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    """
    Delete a professional (admin only).
    """
    professional = db.query(Professional).filter(Professional.id == professional_id).first()
    if not professional:
        raise HTTPException(status_code=404, detail="Professional not found")
    db.delete(professional)
    db.commit()
    return None