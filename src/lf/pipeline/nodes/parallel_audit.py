"""
Nó Parallel Audit: executa AppSec (Security Audit) e DevOps (CI/CD Deployability Analysis)
de forma paralela e simultânea via ThreadPoolExecutor e gera o artefato final lessons.md.
"""
from __future__ import annotations

import concurrent.futures

from ...pipeline.state import GraphState
from .appsec import appsec
from .devops import devops
from .lessons import generate_lessons_md


def parallel_audit(state: GraphState) -> dict:
    """Executa AppSec e DevOps simultaneamente em paralelo e gera o lessons.md."""
    print("--- EXECUTANDO EM PARALELO: AppSec + DevOps Audit ---")

    timeout_seconds = 300
    res_appsec: dict = {}
    res_devops: dict = {}
    worker_errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_appsec = executor.submit(appsec, state)
        future_devops = executor.submit(devops, state)
        future_to_worker = {
            future_appsec: "appsec",
            future_devops: "devops",
        }

        try:
            for future in concurrent.futures.as_completed(
                [future_appsec, future_devops],
                timeout=timeout_seconds,
            ):
                worker = future_to_worker[future]
                try:
                    result = future.result()
                except Exception as exc:
                    worker_errors.append(f"{worker} falhou: {exc}")
                    if worker == "appsec":
                        res_appsec = {"error": f"appsec falhou: {exc}"}
                    else:
                        res_devops = {"error": f"devops falhou: {exc}"}
                    continue

                if worker == "appsec":
                    res_appsec = result
                else:
                    res_devops = result
        except concurrent.futures.TimeoutError:
            for future, worker in future_to_worker.items():
                if not future.done():
                    future.cancel()
                    worker_errors.append(f"{worker} timeout após {timeout_seconds}s")
                    if worker == "appsec":
                        res_appsec = {"error": f"appsec timeout após {timeout_seconds}s"}
                    else:
                        res_devops = {"error": f"devops timeout após {timeout_seconds}s"}

    sec_review = res_appsec.get("security_review") or res_appsec.get("security_report", {})
    sec_report = res_appsec.get("security_report") or sec_review
    ops_report = res_devops.get("devops_report") or res_devops.get("devops_manifest", {})
    ops_manifest = res_devops.get("devops_manifest") or ops_report
    err = res_appsec.get("error") or res_devops.get("error")
    if worker_errors:
        combined_worker_errors = " | ".join(worker_errors)
        err = f"{err} | {combined_worker_errors}" if err else combined_worker_errors

    # Retries de QA esgotados com testes ainda falhando: registrar o erro aqui (no nó),
    # pois mutações no should_retry (aresta condicional) não propagam no LangGraph.
    test_report = state.get("test_report", {})
    tests_failed = (
        test_report.get("summary", {}).get("tests_failed", 1) if isinstance(test_report, dict) else 1
    )
    qa_attempt = state.get("qa_attempt_count", 0)
    max_retries = state.get("max_retries", 3)
    if tests_failed and qa_attempt >= max_retries:
        retry_error = (
            f"QA retries exhausted after {qa_attempt} attempt(s) with failing tests "
            f"(max_retries={max_retries})."
        )
        err = f"{err} | {retry_error}" if err else retry_error

    next_agent = res_appsec.get("next_agent", "FINISH")

    updated_state = {
        **state,
        "security_report": sec_report,
        "security_review": sec_review,
        "devops_report": ops_report,
        "devops_manifest": ops_manifest,
        "next_agent": next_agent if next_agent == "developer" else "FINISH",
        "error": err,
    }

    # Gera o artefato final lessons.md
    generate_lessons_md(updated_state)

    return updated_state
