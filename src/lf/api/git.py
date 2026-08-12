"""Rotas Git (ADE — GitPanel).

Scaffold vazio preenchido pela lane git+health (wave 2).
Padrão: APIRouter prefix /api/v1/git, tags ["Git"].
Autenticação via include_router no app.py (Depends verify_authentication).
"""

from fastapi import APIRouter

git_router = APIRouter(prefix="/api/v1/git", tags=["Git"])
