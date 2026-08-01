"""Aplicação FastAPI principal."""
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title=settings.app_name, version=settings.app_version)

@app.get("/health")
def health() -> dict[str, str]:
    """Endpoint de verificação de saúde da API."""
    return {"status": "ok"}