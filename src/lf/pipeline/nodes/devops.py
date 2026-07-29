#-*- coding: utf-8 -*-
"""Nó DevOps: análise de deployabilidade, geração de Dockerfile e CI workflow."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ...pipeline.state import GraphState


class DevOpsManifest(BaseModel):
    id: str = Field(..., description="DEVOPS-YYYY-MM-DD-001")
    status: str = Field("READY", description="READY ou NOT_READY")
    dockerfile_created: bool = Field(False)
    ci_workflow_created: bool = Field(False)
    deployability_score: float = Field(100.0)
    recommendations: list[str] = Field(default_factory=list)
    execution_timestamp: str = Field(...)


def devops(state: GraphState) -> dict:
    """Nó DevOps: Avalia deployabilidade e propõe/gera Dockerfile e CI."""
    print("---EXECUTANDO NÓ: DevOps (Deployability & CI Analysis)---")

    project_dir = state.get("project_dir", os.getcwd())
    output_dir = state.get("output_dir", ".")
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest_id = f"DEVOPS-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    if state.get("mock_llm"):
        print("--- INFO: DevOps modo MOCK ---")
        manifest = _mock_devops_manifest(manifest_id, now_iso)
        return {**state, "devops_manifest": manifest, "next_agent": "FINISH"}

    dockerfile_exists = os.path.exists(os.path.join(project_dir, "Dockerfile"))
    ci_exists = os.path.exists(os.path.join(project_dir, ".github", "workflows", "ci.yml"))
    pkg_manifest_exists = any(
        os.path.exists(os.path.join(project_dir, f))
        for f in ("pyproject.toml", "setup.py", "requirements.txt", "package.json")
    )

    # Cálculo dinâmico da pontuação de deployabilidade (base 100)
    score = 100.0
    recommendations = []

    if not dockerfile_exists:
        score -= 25.0
        recommendations.append("Adicionar Dockerfile para conteinerização da aplicação.")

    if not ci_exists:
        score -= 25.0
        recommendations.append("Configurar workflow do GitHub Actions em .github/workflows/ci.yml.")

    if not pkg_manifest_exists:
        score -= 20.0
        recommendations.append("Adicionar manifesto de dependências (pyproject.toml ou requirements.txt).")

    qa_report = state.get("test_report", {})
    if qa_report.get("summary", {}).get("tests_failed", 0) > 0:
        score -= 15.0
        recommendations.append("Resolver falhas nos testes unitários antes de realizar deploy.")

    appsec_review = state.get("security_review", {})
    if appsec_review.get("status") == "FAIL":
        score -= 15.0
        recommendations.append("Corrigir vulnerabilidades críticas reportadas pelo AppSec.")

    score = max(0.0, min(100.0, score))
    status_str = "READY" if score >= 70.0 else "NOT_READY"

    # Opt-in seguro para criação de arquivos no projeto
    auto_create = state.get("auto_create_devops_files", False)
    dockerfile_created = False
    ci_created = False

    dockerfile_content = """# Dockerfile otimizado gerado pelo LoopForge DevOps Agent
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["python", "-m", "lf", "serve"]
"""

    ci_content = """name: LoopForge CI Workflow
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: 'pip'
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: Run Linters
        run: ruff check src/
      - name: Run Tests
        run: pytest --cov=src
"""

    if auto_create:
        if not dockerfile_exists:
            dockerfile_path = os.path.join(project_dir, "Dockerfile")
            try:
                with open(dockerfile_path, "w", encoding="utf-8") as f:
                    f.write(dockerfile_content)
                dockerfile_created = True
                print(f"--- INFO: Dockerfile gerado em {dockerfile_path} ---")
            except Exception as e:
                print(f"--- AVISO ao criar Dockerfile: {e} ---")

        if not ci_exists:
            ci_dir = os.path.join(project_dir, ".github", "workflows")
            ci_path = os.path.join(ci_dir, "ci.yml")
            try:
                os.makedirs(ci_dir, exist_ok=True)
                with open(ci_path, "w", encoding="utf-8") as f:
                    f.write(ci_content)
                ci_created = True
                print(f"--- INFO: Workflow CI criado em {ci_path} ---")
            except Exception as e:
                print(f"--- AVISO ao criar CI: {e} ---")
    else:
        print("--- INFO: Criando modelos propostos de Dockerfile e CI no diretório de saída (opt-in desativado) ---")

    # Salva modelos propostos no output_dir em vez de sobrescrever o projeto sem permissão
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "Dockerfile.proposed"), "w", encoding="utf-8") as f:
            f.write(dockerfile_content)
        with open(os.path.join(output_dir, "ci.yml.proposed"), "w", encoding="utf-8") as f:
            f.write(ci_content)

    manifest_model = DevOpsManifest(
        id=manifest_id,
        status=status_str,
        dockerfile_created=dockerfile_created,
        ci_workflow_created=ci_created,
        deployability_score=score,
        recommendations=recommendations or ["Aplicação pronta para deploy."],
        execution_timestamp=now_iso,
    )
    manifest = manifest_model.model_dump()

    if output_dir:
        path = os.path.join(output_dir, f"devops_manifest_{manifest_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Manifesto DevOps salvo em {path} ---")

    return {**state, "devops_manifest": manifest, "next_agent": "FINISH"}


def _mock_devops_manifest(manifest_id: str, timestamp: str) -> dict:
    manifest = DevOpsManifest(
        id=manifest_id,
        status="READY",
        dockerfile_created=True,
        ci_workflow_created=True,
        deployability_score=100.0,
        recommendations=["Configuração DevOps mock finalizada."],
        execution_timestamp=timestamp,
    )
    return manifest.model_dump()
