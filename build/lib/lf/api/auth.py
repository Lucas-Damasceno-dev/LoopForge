"""Módulo de autenticação básica e API Key para a API do LoopForge."""
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

from lf.api.config import APISettings

security_basic = HTTPBasic(auto_error=False)
security_api_key = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_authentication(
    credentials: HTTPBasicCredentials | None = Security(security_basic),
    api_key_header: str | None = Security(security_api_key),
) -> bool:
    """Verifica autenticação via HTTP Basic ou header X-API-Key se ativada."""
    settings = APISettings()

    if not settings.require_auth and not settings.api_key:
        return True

    expected_key = settings.api_key or "secret"

    if api_key_header and secrets.compare_digest(api_key_header, expected_key):
        return True

    if credentials and (
        secrets.compare_digest(credentials.password, expected_key)
        or secrets.compare_digest(credentials.username, expected_key)
    ):
        return True

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou ausentes.",
        headers={"WWW-Authenticate": "Basic"},
    )
