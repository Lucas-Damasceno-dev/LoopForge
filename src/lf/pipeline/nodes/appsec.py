#-*- coding: utf-8 -*-
"""
Nó AppSec: revisão de segurança do código gerado.
Integra com o SecurityScanner e realiza auditoria estática e contextual.
"""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ...guardrails.security_scanner import SecurityScanner
from ...pipeline.state import GraphState


class SecurityVulnerability(BaseModel):
    id: str = Field(..., description="SEC-XXX")
    type: str = Field(..., description="Tipo da vulnerabilidade")
    severity: str = Field("Low", description="Low, Medium, High, Critical")
    file_path: str = Field("")
    line_number: int = Field(0)
    description: str = Field("")


class SecurityReviewReport(BaseModel):
    id: str = Field(..., description="SEC-REV-YYYY-MM-DD-001")
    status: str = Field("PASS", description="PASS ou FAIL")
    vulnerabilities_found: list[SecurityVulnerability] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    execution_timestamp: str = Field(...)


def appsec(state: GraphState) -> dict:
    """Nó AppSec: Executa scanner de segurança e gera relatório."""
    print("---EXECUTANDO NÓ: AppSec (Security Review)---")

    project_dir = state.get("project_dir", os.getcwd())
    now_iso = datetime.now(timezone.utc).isoformat()
    review_id = f"SEC-REV-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    if state.get("mock_llm"):
        print("--- INFO: AppSec modo MOCK ---")
        review = _mock_security_review(review_id, now_iso)
        return {**state, "security_review": review, "next_agent": "devops"}

    # Executa escaneamento estático via SecurityScanner
    scanner = SecurityScanner()
    scanner_vulns = scanner.scan_directory(project_dir)

    vulns = []
    has_critical = False
    for v in scanner_vulns:
        severity = "High" if v.rule_id in ("SEC-001", "SEC-002") else "Medium"
        if severity in ("High", "Critical"):
            has_critical = True
        vulns.append({
            "id": v.rule_id,
            "type": v.message,
            "severity": severity,
            "file_path": v.file_path,
            "line_number": v.line_number,
            "description": f"Vulnerabilidade encontrada na linha {v.line_number}: {v.message}",
        })

    status = "FAIL" if has_critical else "PASS"

    review = {
        "id": review_id,
        "status": status,
        "vulnerabilities_found": vulns,
        "recommendations": [
            "Usar env vars em vez de chaves de API hardcoded",
            "Evitar eval() e exec() dinâmicos em código de produção",
        ] if vulns else ["Nenhuma vulnerabilidade crítica identificada"],
        "execution_timestamp": now_iso,
    }

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"security_review_{review_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(review, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Relatório AppSec salvo em {path} ---")

    if status == "FAIL":
        print("--- AVISO: Vulnerabilidades críticas encontradas! Notificando Developer. ---")
        state["feedback_history"] = state.get("feedback_history", []) + [
            {
                "from": "appsec",
                "message": f"AppSec encontrou {len(vulns)} vulnerabilidade(s). Favor corrigir.",
                "timestamp": now_iso,
            }
        ]
        return {**state, "security_review": review, "next_agent": "developer"}

    return {**state, "security_review": review, "next_agent": "devops"}


def _mock_security_review(review_id: str, timestamp: str) -> dict:
    return {
        "id": review_id,
        "status": "PASS",
        "vulnerabilities_found": [],
        "recommendations": ["Nenhuma vulnerabilidade encontrada (mock)."],
        "execution_timestamp": timestamp,
    }
