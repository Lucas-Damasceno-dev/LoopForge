"""Configuração oficial da API REST e Web UI do LoopForge."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import TypeAdapter, ValidationError
from pydantic_settings import BaseSettings

from lf.config.loader import load_ade_config, save_ade_config
from lf.config.schema import AdeConfig, AdeMcpServer

config_router = APIRouter(prefix="/api/v1/config", tags=["Config"])


def _ade_yaml() -> Path:
    """Caminho do ade.yaml resolvido em call-time (não import-time).

    Respeita os.chdir()/monkeypatch.chdir usado pelos testes e pela CLI em
    diretórios de trabalho arbitrários (mesmo padrão de _trajectories_db).
    """
    return Path(".loopforge/ade.yaml").resolve()


@config_router.get("")
async def get_config() -> AdeConfig:
    return load_ade_config(_ade_yaml())


@config_router.patch("")
async def patch_config(payload: dict):
    current = load_ade_config(_ade_yaml())
    merged = current.model_copy(deep=True)
    try:
        for key, value in payload.items():
            if not hasattr(merged, key):
                continue
            annotation = merged.__class__.__annotations__.get(key)
            if isinstance(value, dict) and annotation is not None:
                # Sub-modelos aninhados (AdeHITL, AdeProviders, etc.) são
                # reconstruídos com validação pydantic (422 se inválido).
                setattr(merged, key, annotation(**value))
            elif key == "mcp_servers" and isinstance(value, list):
                # D3 (Fase D): lista de servers é reconstruída como
                # list[AdeMcpServer] VALIDADA (antes era setada crua — itens
                # inválidos eram silenciosamente descartados pelo serializer).
                setattr(merged, key, TypeAdapter(list[AdeMcpServer]).validate_python(value))
            else:
                setattr(merged, key, value)
        validated = AdeConfig(**merged.model_dump())
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    save_ade_config(validated, _ade_yaml())
    return validated


class APISettings(BaseSettings):
    """Configurações da API do LoopForge.

    Usa banco único (.loopforge/telemetry.sqlite) por padrão.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Banco de dados único (SQLite compartilhado com telemetry por padrão)
    database_url: str = "sqlite+aiosqlite:///.loopforge/telemetry.sqlite"

    # Autenticação básica / API Key (desativada por padrão — ative via .env)
    api_key: str | None = None
    require_auth: bool = False

    # CORS (M-04): default "*" (wildcard). LF_CORS_ORIGINS lista origens
    # separadas por vírgula, ex.: "http://localhost:5173,https://app.example.com".
    cors_origins: str = "*"

    # Pool de conexões (usado quando PostgreSQL for fornecido)
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = {"env_prefix": "LF_API_", "env_file": ".env", "extra": "ignore"}

    def cors_origins_list(self) -> list[str]:
        """Origens CORS efetivas (env LF_CORS_ORIGINS ou default do settings)."""
        raw = os.getenv("LF_CORS_ORIGINS") or self.cors_origins
        return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_api_settings() -> APISettings:
    """Retorna instância de APISettings avaliada dinamicamente."""
    return APISettings()
