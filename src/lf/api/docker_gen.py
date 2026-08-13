"""Gerador de configurações Docker, docker-compose e devcontainer para o workspace de uma Run.

Analisa a stack e os arquivos gerados no workspace da run para produzir templates
otimizados e prontos para containerização e desenvolvimento em containers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from lf.api.database import session_factory
from lf.api.models import PipelineRun
from lf.api.schemas import DockerConfigResponse, SaveDockerConfigRequest, SaveDockerConfigResponse

docker_router = APIRouter(prefix="/api/v1/docker", tags=["docker"])

_RUNS_ROOT = Path("/tmp/loopforge")


def _get_run_workspace(run_id: str) -> Path:
    return _RUNS_ROOT / f"run_{run_id}"


def _detect_database_need(workspace: Path) -> bool:
    """Verifica se o projeto usa banco de dados relacional (Postgres, SQLAlchemy, psycopg, etc)."""
    if not workspace.exists():
        return False
    keywords = ["sqlalchemy", "psycopg", "postgres", "database_url", "alembic", "prisma", "hibernate"]
    for path in workspace.rglob("*"):
        if path.is_file() and path.suffix in [".py", ".ts", ".js", ".java", ".env", ".toml"]:
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
                if any(kw in content for kw in keywords):
                    return True
            except Exception:
                continue
    return False


def _generate_python_docker(run_id: str, uses_db: bool) -> dict[str, Any]:
    base_image = "python:3.12-slim"
    suggested_ports = [8000]
    env_vars = {
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PORT": "8000",
    }
    if uses_db:
        env_vars["DATABASE_URL"] = "postgresql://postgres:postgres@db:5432/app_db"

    dockerfile = f"""# syntax=docker/dockerfile:1
FROM {base_image} AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    curl \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements*.txt pyproject.toml* ./
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy source code
COPY . .

# Run as non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""

    db_service = """
  db:
    image: postgres:16-alpine
    container_name: loopforge-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: app_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
""" if uses_db else ""

    volume_def = """
volumes:
  postgres_data:
""" if uses_db else ""

    docker_compose = f"""version: "3.8"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: app-{run_id[:8]}
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      {"- DATABASE_URL=postgresql://postgres:postgres@db:5432/app_db" if uses_db else ""}
    {"depends_on:\\n      - db" if uses_db else ""}
    volumes:
      - .:/app
{db_service}{volume_def}"""

    devcontainer = {
        "name": f"LoopForge Python ({run_id[:8]})",
        "image": base_image,
        "customizations": {
            "vscode": {
                "extensions": [
                    "ms-python.python",
                    "ms-python.vscode-pylance",
                    "ms-python.black-formatter",
                    "charliermarsh.ruff",
                ],
                "settings": {
                    "python.formatting.provider": "none",
                    "[python]": {
                        "editor.defaultFormatter": "charliermarsh.ruff",
                        "editor.formatOnSave": True,
                    },
                },
            }
        },
        "forwardPorts": suggested_ports,
        "postCreateCommand": "pip install -r requirements.txt || pip install -e .",
    }

    dockerignore = """.git
.venv
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.coverage
htmlcov
dist
build
*.egg-info
.env
"""

    return {
        "base_image": base_image,
        "dockerfile": dockerfile.strip(),
        "docker_compose": docker_compose.strip(),
        "devcontainer": json.dumps(devcontainer, indent=2),
        "dockerignore": dockerignore.strip(),
        "suggested_ports": suggested_ports,
        "environment_vars": env_vars,
    }


def _generate_generic_docker(stack: str, run_id: str, uses_db: bool) -> dict[str, Any]:
    if stack in ["react", "typescript", "node", "javascript"]:
        base_image = "node:20-alpine"
        suggested_ports = [3000, 5173]
        env_vars = {"NODE_ENV": "development", "PORT": "3000"}

        dockerfile = f"""FROM {base_image} AS base

WORKDIR /app

COPY package*.json ./
RUN npm ci || npm install

COPY . .

EXPOSE 3000 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
"""
        devcontainer = {
            "name": f"LoopForge Node ({run_id[:8]})",
            "image": base_image,
            "customizations": {
                "vscode": {
                    "extensions": [
                        "dbaeumer.vscode-eslint",
                        "esbenp.prettier-vscode",
                    ]
                }
            },
            "forwardPorts": suggested_ports,
            "postCreateCommand": "npm install",
        }
        dockerignore = "node_modules\n.git\ndist\nbuild\n.env\n"
    elif stack in ["rust"]:
        base_image = "rust:1.78-slim"
        suggested_ports = [8080]
        env_vars = {"RUST_LOG": "info"}
        dockerfile = f"""FROM {base_image} AS builder
WORKDIR /app
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
WORKDIR /app
COPY --from=builder /app/target/release/* /app/
CMD ["./app"]
"""
        devcontainer = {
            "name": f"LoopForge Rust ({run_id[:8]})",
            "image": base_image,
            "customizations": {
                "vscode": {"extensions": ["rust-lang.rust-analyzer"]}
            },
            "forwardPorts": suggested_ports,
        }
        dockerignore = "target\n.git\n"
    else:
        # Fallback Python / Standard
        return _generate_python_docker(run_id, uses_db)

    docker_compose = f"""version: "3.8"

services:
  app:
    build: .
    container_name: app-{run_id[:8]}
    ports:
      - "3000:3000"
    volumes:
      - .:/app
"""

    return {
        "base_image": base_image,
        "dockerfile": dockerfile.strip(),
        "docker_compose": docker_compose.strip(),
        "devcontainer": json.dumps(devcontainer, indent=2),
        "dockerignore": dockerignore.strip(),
        "suggested_ports": suggested_ports,
        "environment_vars": env_vars,
    }


@docker_router.get("/{run_id}", response_model=DockerConfigResponse)
async def get_docker_config(run_id: str) -> DockerConfigResponse:
    """Gera arquivos Dockerfile, docker-compose.yml e devcontainer.json para a run."""
    async with session_factory() as session:
        stmt = select(PipelineRun).where(PipelineRun.id == run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' não encontrada")

    workspace = _get_run_workspace(run_id)
    uses_db = _detect_database_need(workspace)
    stack = (run.stack or "python").lower()

    if "python" in stack or "fastapi" in stack:
        gen = _generate_python_docker(run_id, uses_db)
    else:
        gen = _generate_generic_docker(stack, run_id, uses_db)

    return DockerConfigResponse(
        run_id=run_id,
        stack=run.stack or "python",
        base_image=gen["base_image"],
        dockerfile=gen["dockerfile"],
        docker_compose=gen["docker_compose"],
        devcontainer=gen["devcontainer"],
        dockerignore=gen["dockerignore"],
        suggested_ports=gen["suggested_ports"],
        environment_vars=gen["environment_vars"],
    )


@docker_router.post("/{run_id}/save", response_model=SaveDockerConfigResponse)
async def save_docker_config(run_id: str, payload: SaveDockerConfigRequest) -> SaveDockerConfigResponse:
    """Salva os arquivos Docker gerados/customizados diretamente no workspace da run."""
    async with session_factory() as session:
        stmt = select(PipelineRun).where(PipelineRun.id == run_id)
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Run '{run_id}' não encontrada")

    workspace = _get_run_workspace(run_id)
    workspace.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    if payload.dockerfile:
        (workspace / "Dockerfile").write_text(payload.dockerfile, encoding="utf-8")
        saved.append("Dockerfile")

    if payload.docker_compose:
        (workspace / "docker-compose.yml").write_text(payload.docker_compose, encoding="utf-8")
        saved.append("docker-compose.yml")

    if payload.dockerignore:
        (workspace / ".dockerignore").write_text(payload.dockerignore, encoding="utf-8")
        saved.append(".dockerignore")

    if payload.devcontainer:
        dev_dir = workspace / ".devcontainer"
        dev_dir.mkdir(parents=True, exist_ok=True)
        (dev_dir / "devcontainer.json").write_text(payload.devcontainer, encoding="utf-8")
        saved.append(".devcontainer/devcontainer.json")

    return SaveDockerConfigResponse(
        run_id=run_id,
        success=True,
        saved_files=saved,
        message=f"{len(saved)} arquivos de configuração Docker salvos no workspace.",
    )
