"""Testes do nó Developer em modo incremental (milestone v7 5.1).

Verifica o escopo da story por slice (prompt só do slice corrente), o avanço
de slice_index quando o slice anterior passou e a propagação de slices no
retorno. Usa call_llm_via_opencode patchado (determinístico).
"""

from pathlib import Path
from unittest.mock import patch

from lf.pipeline.nodes.developer import developer
from lf.pipeline.nodes.slices import build_slices

CANNED_RESPONSE = """### FILE: generated_code.py
```python
def main():
    return 1
```
### FILE: pyproject.toml
```toml
[build-system]
requires = ["setuptools"]
```
"""


def _stories() -> list[dict]:
    return [
        {
            "id": "E-001-US001",
            "title": "Funcionalidade principal",
            "epic_id": "E-001",
            "acceptance_criteria": ["Dado que...", "Então..."],
            "priority": "High",
            "status": "Pending",
        },
        {
            "id": "E-001-US002",
            "title": "Relatório avançado",
            "epic_id": "E-001",
            "acceptance_criteria": ["Quando...", "Então..."],
            "priority": "Medium",
            "status": "Pending",
        },
    ]


def _developer_state(tmp_path: Path, slices: list[dict], slice_index: int, slice_status: str) -> dict:
    return {
        "idea": "Feature slice",
        "stack": "python",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "tech_spec": "Spec",
        "user_stories": _stories(),
        "slices": slices,
        "slice_index": slice_index,
        "slice_status": slice_status,
        "incremental_slices": True,
        "contract_tests": "",
        "code": "",
        "test_report": {},
        "feedback_history": [],
        "attempt_count": 0,
        "qa_attempt_count": 0,
        "max_retries": 3,
        "read_only": False,
        "complexity_level": "standard",
        "mock_llm": False,
    }


def test_developer_slice_scoped_prompt_e_avanca(tmp_path):
    slices = build_slices(_stories())
    captured: dict = {}

    def _fake_llm(**kwargs):
        captured["user_prompt"] = kwargs.get("user_prompt", "")
        return CANNED_RESPONSE

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_llm):
        # 1ª chamada: slice 0 (US001) — story 0 no prompt, US002 ausente
        out0 = developer(_developer_state(tmp_path, slices, slice_index=0, slice_status=""))
        assert "E-001-US001" in captured["user_prompt"]
        assert "E-001-US002" not in captured["user_prompt"]
        assert out0["slice_index"] == 0
        assert out0["slices"][0]["attempts"] == 1
        assert out0["slice_status"] == "pending"

        # QA aprovou o slice 0 → slice_status "passed" → avança para o slice 1
        out1 = developer(_developer_state(tmp_path, out0["slices"], slice_index=0, slice_status="passed"))
        assert out1["slice_index"] == 1
        assert "E-001-US002" in captured["user_prompt"]
        assert "E-001-US001" not in captured["user_prompt"]
        assert out1["slices"][1]["attempts"] == 1
        assert out1["slice_status"] == "pending"


def test_developer_retry_mesmo_slice_nao_avanca(tmp_path):
    slices = build_slices(_stories())
    # Slice 0 falhou no QA (slice_status "failed") → retry do MESMO slice
    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", return_value=CANNED_RESPONSE):
        out = developer(_developer_state(tmp_path, slices, slice_index=0, slice_status="failed"))
    assert out["slice_index"] == 0
    assert out["slices"][0]["attempts"] == 1


def test_developer_sem_incremental_prompt_usa_todas_stories(tmp_path):
    state = {
        "idea": "Feature slice",
        "stack": "python",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "tech_spec": "Spec",
        "user_stories": _stories(),
        "incremental_slices": False,
        "contract_tests": "",
        "code": "",
        "test_report": {},
        "feedback_history": [],
        "attempt_count": 0,
        "qa_attempt_count": 0,
        "max_retries": 3,
        "read_only": False,
        "complexity_level": "standard",
        "mock_llm": False,
    }
    captured: dict = {}

    def _fake_llm(**kwargs):
        captured["user_prompt"] = kwargs.get("user_prompt", "")
        return CANNED_RESPONSE

    with patch("lf.pipeline.nodes.developer.call_llm_via_opencode", side_effect=_fake_llm):
        out = developer(state)
    assert "E-001-US001" in captured["user_prompt"]
    assert "E-001-US002" in captured["user_prompt"]
    # Flag off: developer NÃO adiciona canais de slice no retorno
    assert "slices" not in out
    assert "slice_index" not in out
    assert "slice_status" not in out
