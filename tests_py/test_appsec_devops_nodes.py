import pytest
import os
from pathlib import Path
from lf.pipeline.nodes.appsec import appsec
from lf.pipeline.nodes.devops import devops


def test_appsec_node_mock(tmp_path):
    state = {
        "mock_llm": True,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res = appsec(state)
    assert res["next_agent"] == "devops"
    assert "security_review" in res
    assert res["security_review"]["status"] == "PASS"


def test_appsec_node_vulnerabilities(tmp_path):
    # Write vulnerable file with eval()
    vuln_file = tmp_path / "app.py"
    vuln_file.write_text("eval('1 + 1')\n", encoding="utf-8")

    state = {
        "mock_llm": False,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res = appsec(state)
    assert res["next_agent"] == "developer"
    assert res["security_review"]["status"] == "FAIL"
    assert len(res["security_review"]["vulnerabilities_found"]) == 1


def test_devops_node(tmp_path):
    state = {
        "mock_llm": False,
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
    }
    res = devops(state)
    assert res["next_agent"] == "FINISH"
    assert "devops_manifest" in res
    assert (tmp_path / "Dockerfile").exists()
    assert (tmp_path / ".github" / "workflows" / "ci.yml").exists()
