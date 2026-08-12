"""API de memória e lições aprendidas (ADE — MemoryPanel).

Scaffold: router vazio, implementado pela lane de memória (engine + ADE).
Contrato previsto:
  GET    /api/v1/memory/lessons?stack=&query=&limit=  → lista + busca
  POST   /api/v1/memory/lessons                       → cria
  PATCH  /api/v1/memory/lessons/{id}                  → atualiza
  DELETE /api/v1/memory/lessons/{id}                  → remove
Auth aplicada no include (app.py), padrão dos demais routers.
"""

from fastapi import APIRouter

memory_router = APIRouter(prefix="/api/v1/memory", tags=["Memory"])
