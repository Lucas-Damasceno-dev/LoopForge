from unittest.mock import patch

from lf.pipeline.nodes.parallel_audit import parallel_audit


def test_appsec_retry_cycle_routing(tmp_path):
    """Garante que quando AppSec detecta falha e solicita retentativa, o grafo redireciona para o Developer."""
    initial_state = {
        "idea": "API com vulnerabilidade SQLi",
        "stack": "python",
        "mock_llm": True,
        "output_dir": str(tmp_path),
        "user_stories": [{"id": "US1", "title": "API Endpoint"}],
        "qa_attempt_count": 1,
        "appsec_attempt_count": 0,
        "max_retries": 3,
        "next_agent": "developer",
    }

    mock_appsec_fail = {
        "security_review": {
            "status": "FAIL",
            "vulnerabilities_found": [
                {"severity": "CRITICAL", "type": "SQL Injection", "description": "Uso de exec/eval"}
            ],
        },
        "appsec_attempt_count": 1,
        "next_agent": "developer",
    }

    with patch("lf.pipeline.nodes.parallel_audit.appsec", return_value=mock_appsec_fail):
        result_audit = parallel_audit(initial_state)
        assert result_audit["next_agent"] == "developer"
