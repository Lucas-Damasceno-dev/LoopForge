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

    # Consolida os resultados das execuções paralelas sem mutação de estado
    sec_report = res_appsec.get("security_report", {})
    ops_report = res_devops.get("devops_report", {})
    err = res_appsec.get("error") or res_devops.get("error")

    # Se AppSec reprovar, o destino é retentativa pelo developer, senão finaliza (FINISH)
    next_agent = res_appsec.get("next_agent", "FINISH")

    return {
        **state,
        "security_report": sec_report,
        "devops_report": ops_report,
        "next_agent": next_agent if next_agent == "developer" else "FINISH",
        "error": err,
    }
