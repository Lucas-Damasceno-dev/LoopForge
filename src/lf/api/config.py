"""Configuração oficial da API REST e Web UI do LoopForge."""
from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    """Configurações da API do LoopForge.

    Usa banco único (.loopforge/telemetry.sqlite) por padrão.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    # Banco de dados único (SQLite compartilhado com telemetry por padrão)
    database_url: str = "sqlite+aiosqlite:///.loopforge/telemetry.sqlite"

    # Autenticação básica / API Key (opcional)
    api_key: str | None = None
    require_auth: bool = False

    # Pool de conexões (usado quando PostgreSQL for fornecido)
    db_pool_size: int = 5
    db_max_overflow: int = 10

    model_config = {"env_prefix": "LF_API_", "env_file": ".env", "extra": "ignore"}
