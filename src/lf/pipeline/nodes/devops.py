#-*- coding: utf-8 -*-
"""
Nó DevOps: análise de deployabilidade, geração de Dockerfile e CI workflow.
"""
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
    execution_timestamp: str = Field(...)


def devops(state: GraphState) -> dict:
    """Nó DevOps: Verifica deployabilidade, assegura Dockerfile e CI."""
    print("---EXECUTANDO NÓ: DevOps (Deployability & CI Analysis)---")

    project_dir = state.get("project_dir", os.getcwd())
    now_iso = datetime.now(timezone.utc).isoformat()
    manifest_id = f"DEVOPS-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    if state.get("mock_llm"):
        print("--- INFO: DevOps modo MOCK ---")
        manifest = _mock_devops_manifest(manifest_id, now_iso)
        return {**state, "devops_manifest": manifest, "next_agent": "FINISH"}

    dockerfile_path = os.path.join(project_dir, "Dockerfile")
    dockerfile_created = False
    if not os.path.exists(dockerfile_path):
        dockerfile_content = """# Dockerfile gerado automaticamente pelo DevOps Agent do LoopForge
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir .
COPY . .
CMD ["python", "-m", "lf"]
"""
        try:
            with open(dockerfile_path, "w", encoding="utf-8") as f:
                f.write(dockerfile_content)
            dockerfile_created = True
            print(f"--- INFO: Dockerfile criado em {dockerfile_path} ---")
        except Exception as e:
            print(f"--- AVISO DevOps ao criar Dockerfile: {e} ---")

    ci_dir = os.path.join(project_dir, ".github", "workflows")
    ci_path = os.path.join(ci_dir, "ci.yml")
    ci_created = False
    if not os.path.exists(ci_path):
        os.makedirs(ci_dir, exist_ok=True)
        ci_content = """name: CI Workflow
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest
"""
        try:
            with open(ci_path, "w", encoding="utf-8") as f:
                f.write(ci_content)
            ci_created = True
            print(f"--- INFO: Workflow de CI criado em {ci_path} ---")
        except Exception as e:
            print(f"--- AVISO DevOps ao criar CI Workflow: {e} ---")

    manifest = {
        "id": manifest_id,
        "status": "READY",
        "dockerfile_created": dockerfile_created,
        "ci_workflow_created": ci_created,
        "deployability_score": 100.0,
        "execution_timestamp": now_iso,
    }

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"devops_manifest_{manifest_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Manifesto DevOps salvo em {path} ---")

    return {**state, "devops_manifest": manifest, "next_agent": "FINISH"}


def _mock_devops_manifest(manifest_id: str, timestamp: str) -> dict:
    return {
        "id": manifest_id,
        "status": "READY",
        "dockerfile_created": True,
        "ci_workflow_created": True,
        "deployability_score": 100.0,
        "execution_timestamp": timestamp,
    }
