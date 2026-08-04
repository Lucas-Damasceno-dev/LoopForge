"""Rotas de autenticação."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models import User
from app.schemas import LoginRequest, Token, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Realiza login e retorna um token JWT."""
    email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    token = create_access_token(user.id, user.role)
    return Token(access_token=token, token_type="bearer")


@router.post("/logout")
def logout() -> dict[str, str]:
    """Encerra a sessão no cliente.

    O JWT é stateless; o logout apenas instrui o cliente a descartar o token.
    """
    return {"message": "Logout realizado. Descarte o token no cliente."}


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    """Registra um novo usuário cliente."""
    if payload.role != "client":
        raise HTTPException(status_code=400, detail="Registro público disponível apenas para clientes.")

    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    user = User(
        name=payload.name.strip(),
        email=email,
        password_hash=get_password_hash(payload.password),
        role="client",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user