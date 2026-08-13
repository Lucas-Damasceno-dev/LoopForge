"""Testes do guard de limpeza no retry incremental (milestone v7 5.1).

Em modo incremental o retry NÃO chama _cleanup_stale_project_dirs — os slices
anteriores são acumulados de propósito (o QA detecta regressão comparando o
slice novo contra os antigos). Flag off preserva a limpeza legada.
"""

from pathlib import Path
from unittest.mock import patch

from lf.pipeline.nodes.developer import developer

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


def _state(tmp_path: Path, incremental: bool) -> dict:
    return {
        "idea": "Feature",
        "stack": "python",
        "output_dir": str(tmp_path),
        "project_dir": str(tmp_path),
        "tech_spec": "Spec",
        "user_stories": [],
        "slices": [],
        "slice_index": 0,
        "slice_status": "failed",
        "incremental_slices": incremental,
        "contract_tests": "",
        "code": "",
        "test_report": {},
        "feedback_history": [],
        "attempt_count": 0,
        "qa_attempt_count": 1,  # retry (QA já falhou uma vez)
        "max_retries": 3,
        "read_only": False,
        "complexity_level": "standard",
        "mock_llm": False,
    }


def test_retry_incremental_nao_limpa_accumulado(tmp_path):
    with (
        patch("lf.pipeline.nodes.developer.call_llm_via_opencode", return_value=CANNED_RESPONSE),
        patch("lf.pipeline.nodes.developer._cleanup_stale_project_dirs") as spy,
    ):
        out = developer(_state(tmp_path, incremental=True))
    assert not out.get("error")
    spy.assert_not_called()


def test_retry_whole_feature_limpa(tmp_path):
    with (
        patch("lf.pipeline.nodes.developer.call_llm_via_opencode", return_value=CANNED_RESPONSE),
        patch("lf.pipeline.nodes.developer._cleanup_stale_project_dirs") as spy,
    ):
        out = developer(_state(tmp_path, incremental=False))
    assert not out.get("error")
    spy.assert_called_once()
