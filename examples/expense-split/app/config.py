"""Configurações da aplicação carregadas de variáveis de ambiente."""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Configurações tipadas da aplicação.

    Atributos:
        app_name: Nome público da aplicação.
        app_version: Versão atual da aplicação.
        environment: Ambiente de execução (development, staging, production).
        database_url: URL de conexão com o PostgreSQL.
        email_sender: Remetente padrão de e-mails.
        invite_expiration_days: Validade em dias dos convites.
        settlement_algorithm: Algoritmo usado para liquidação de saldos.
    """

    app_name: str = "Expense Splitter API"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://expense:expense@localhost:5432/expense_splitter"
    email_sender: str = "no-reply@expense-splitter.local"
    invite_expiration_days: int = 7
    settlement_algorithm: str = "greedy"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()