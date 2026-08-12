"""Rotas Prompt Central (ADE — PromptPanel).

Scaffold vazio preenchido pela lane prompt central (wave 2).
Padrão: APIRouter prefix /api/v1/prompts, tags ["Prompts"].
Autenticação via include_router no app.py (Depends verify_authentication).
"""

from fastapi import APIRouter

prompts_router = APIRouter(prefix="/api/v1/prompts", tags=["Prompts"])
