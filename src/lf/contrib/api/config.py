"""Configuração da API via Pydantic Settings."""

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Configurações da API REST do LoopForge.

    Carregadas de variáveis de ambiente ou arquivo .env.
    """

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Banco de dados PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/loopforge"

    # Pool de conexões
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = {"env_prefix": "LF_API_", "env_file": ".env", "extra": "ignore"}