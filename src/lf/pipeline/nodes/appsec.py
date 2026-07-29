#-*- coding: utf-8 -*-
"""Nó AppSec: revisão de segurança estática e contextual com LLM do código gerado."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ...guardrails.security_scanner import SecurityScanner
from ...pipeline.state import GraphState
from ...runner.opencode.llm import call_llm_via_opencode


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
    """Nó AppSec: Executa scanner estático e revisão contextual via LLM."""
    print("---EXECUTANDO NÓ: AppSec (Security Review)---")

    project_dir = state.get("project_dir", os.getcwd())
    now_iso = datetime.now(timezone.utc).isoformat()
    review_id = f"SEC-REV-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}-001"

    if state.get("mock_llm"):
        print("--- INFO: AppSec modo MOCK ---")
        review = _mock_security_review(review_id, now_iso)
        return {**state, "security_review": review, "next_agent": "devops"}

    # 1. Escaneamento estático via SecurityScanner
    scanner = SecurityScanner()
    scanner_vulns = scanner.scan_directory(project_dir)

    vulns: list[SecurityVulnerability] = []
    has_critical_or_high = False

    for v in scanner_vulns:
        if v.rule_id == "SEC-001":
            severity = "Critical"
        elif v.rule_id == "SEC-002":
            severity = "Critical"
        elif v.rule_id == "SEC-003":
            severity = "High"
        else:
            severity = "Medium"

        if severity in ("High", "Critical"):
            has_critical_or_high = True

        vulns.append(
            SecurityVulnerability(
                id=v.rule_id,
                type=v.message,
                severity=severity,
                file_path=v.file_path,
                line_number=v.line_number,
                description=f"Vulnerabilidade [{severity}] na linha {v.line_number}: {v.message}",
            )
        )

    # 2. Revisão contextual via LLM se o scanner estático passar
    recommendations = [
        "Usar variáveis de ambiente (.env) para segredos",
        "Evitar eval() / exec() e sanitizar argumentos de comandos",
    ]
    if not vulns:
        code_snippet = state.get("code", "")[:2000]
        if code_snippet:
            try:
                prompt = (
                    "Analise o código abaixo buscando falhas de segurança de negócios, OWASP Top 10, "
                    "vulnerabilidades de injeção ou controle de acesso. Se seguro, diga SEGURO.\n\n"
                    f"Código:\n```python\n{code_snippet}\n```"
                )
                llm_res = call_llm_via_opencode(
                    system_prompt="Você é um engenheiro de AppSec sênior especializado em segurança de código.",
                    user_prompt=prompt,
                    mock=state.get("mock_llm", False),
                )
                recommendations.append(f"Análise LLM AppSec: {str(llm_res)[:150]}")
            except Exception as e:
                print(f"--- AVISO: Erro na análise LLM AppSec ({e}) ---")

    status = "FAIL" if has_critical_or_high else "PASS"

    report_model = SecurityReviewReport(
        id=review_id,
        status=status,
        vulnerabilities_found=vulns,
        recommendations=recommendations if vulns else ["Nenhuma vulnerabilidade crítica identificada"],
        execution_timestamp=now_iso,
    )
    review = report_model.model_dump()

    output_dir = state.get("output_dir", ".")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"security_review_{review_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(review, f, indent=2, ensure_ascii=False)
        print(f"--- INFO: Relatório AppSec salvo em {path} ---")

    if status == "FAIL":
        print("--- AVISO: Vulnerabilidades críticas/altas encontradas! Notificando Developer. ---")
        state["feedback_history"] = state.get("feedback_history", []) + [
            {
                "from": "appsec",
                "message": f"AppSec encontrou {len(vulns)} vulnerabilidade(s) Críticas/Altas. Favor corrigir.",
                "timestamp": now_iso,
            }
        ]
        return {**state, "security_review": review, "next_agent": "developer"}

    return {**state, "security_review": review, "next_agent": "devops"}


def _mock_security_review(review_id: str, timestamp: str) -> dict:
    report = SecurityReviewReport(
        id=review_id,
        status="PASS",
        vulnerabilities_found=[],
        recommendations=["Nenhuma vulnerabilidade encontrada (mock)."],
        execution_timestamp=timestamp,
    )
    return report.model_dump()
