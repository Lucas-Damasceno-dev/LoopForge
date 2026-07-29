"""
Nó Parallel Audit: executa AppSec (Security Audit) e DevOps (CI/CD Deployability Analysis)
de forma paralela e simultânea via ThreadPoolExecutor.
"""
from __future__ import annotations

import concurrent.futures

from ...pipeline.state import GraphState
from .appsec import appsec
from .devops import devops


def parallel_audit(state: GraphState) -> dict:
    """Executa AppSec e DevOps simultaneamente em paralelo."""
    print("--- EXECUTANDO EM PARALELO: AppSec + DevOps Audit ---")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_appsec = executor.submit(appsec, state)
        future_devops = executor.submit(devops, state)

        res_appsec = future_appsec.result()
        res_devops = future_devops.result()

    sec_review = res_appsec.get("security_review") or res_appsec.get("security_report", {})
    sec_report = res_appsec.get("security_report") or sec_review
    ops_report = res_devops.get("devops_report") or res_devops.get("devops_manifest", {})
    ops_manifest = res_devops.get("devops_manifest") or ops_report
    err = res_appsec.get("error") or res_devops.get("error")

    next_agent = res_appsec.get("next_agent", "FINISH")

    return {
        **state,
        "security_report": sec_report,
        "security_review": sec_review,
        "devops_report": ops_report,
        "devops_manifest": ops_manifest,
        "next_agent": next_agent if next_agent == "developer" else "FINISH",
        "error": err,
    }
